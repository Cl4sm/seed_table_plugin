import asyncio
import ctypes
import psycopg2
import threading

from time import sleep
from typing import Dict, List
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy import func, literal


try:
    from slacrs import Slacrs
    from slacrs.model import Input, InputTag
except ImportError as ex:
    Slacrs = None


class Seed:
    def __init__(self, seed: Input, id: int):
        self.created_at = seed.created_at
        self.tags: List[str] = [x.value for x in seed.tags]
        self.value: bytes = seed.value
        self._realid = seed.id
        self.id: str = hex(id)[2:].rjust(8, "0")

class SeedQueryThread(threading.Thread):
    def __init__(self, instance, inp, tags, offset, size, page_no, seed_callback):
        threading.Thread.__init__(self)
        self.instance = instance
        self.inp = inp
        self.tags = tags
        self.offset = offset
        self.size = size
        self.page_no = page_no
        self.seed_callback = seed_callback

    def run(self):
        try:
            session = self.instance.session()
            self.query_seeds(session, self.inp, self.tags, self.offset, self.size)
        except Exception as e:
            conn = session.connection()
            conn.connection.cancel()
            session.close()

    def get_id(self):
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for id, thread in threading._active.items():
            if thread is self:
                return id

    def kill_query(self):
        thread_id = self.get_id()
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
              ctypes.py_object(SystemExit))

    def query_seeds(self, session, inp: bytes, tags: List[str], offset: int, size: int):
        seeds: List[Seed] = []
        if session:
            query = session.query(Input, func.count(Input.id).over().label('total'))

            if inp:
                if isinstance(session.bind.dialect, postgresql.dialect):
                    query = query.filter(func.POSITION(literal(inp).op('in')(Input.value)) != 0)
                elif isinstance(session.bind.dialect, sqlite.dialect):
                    pass

            if tags:
                query = query.join(Input.tags)
                for tag in tags:
                    query = query.filter(Input.tags.any(InputTag.value == tag))

            result = query.order_by(Input.created_at).limit(size).offset(offset).all()
            count = result[0][1] if len(result) > 0 else 0
            seeds = [Seed(seed[0], idx) for idx, seed in enumerate(result)]
            session.close()
            self.seed_callback(seeds, count=count, page_no=self.page_no)

class SeedTable:
    """
    Multiple POIs
    """
    query_signal = None

    def __init__(self, workspace, query_signal, seed_callback=None):
        self.workspace = workspace
        self.seed_callback = seed_callback
        self.connector = None
        self.slacrs_instance = None
        self.should_exit = False
        self.query_signal = query_signal
        self.is_querying = False

        self.init_instance()

        self.slacrs_thread = threading.Thread(target=self.listen_for_events)
        self.slacrs_thread.setDaemon(True)
        self.slacrs_thread.start()
        self.query_thread = None


    def init_instance(self) -> bool:
        self.connector = self.workspace.plugins.get_plugin_instance_by_name("ChessConnector")

        if self.connector is None:
            self.workspace.log("Unable to retrieve plugin ChessConnector")
            return False

        self.slacrs_instance = self.connector.slacrs_instance()

        if self.slacrs_instance is None:
            self.workspace.log("Unable to retrieve Slacrs instance")
            return False

        return True


    def listen_for_events(self):
        asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
        while not self.connector:
            self.connector = self.workspace.plugins.get_plugin_instance_by_name("ChessConnector")
            sleep(1)

        while not self.slacrs_instance:
            self.slacrs_instance = self.connector.slacrs_instance()
            sleep(1)

        while not self.connector.target_image_id:
            sleep(1)

        self.get_seeds()
        self.query_thread.join()

        prev_target = self.connector.target_image_id
        while not self.should_exit:
            if self.connector.target_image_id != prev_target:
                prev_target = self.connector.target_image_id
                self.get_seeds()
                self.query_thread.join()

            new_event_count = self.slacrs_instance.fetch_events()
            for _ in range(new_event_count):
                e = self.slacrs_instance.event_queue.get_nowait()
                session = self.slacrs_instance.session()
                if e.kind == "input":
                    obj = e.get_object(session)
                    if session.query(Input).filter_by(id=e.object_id).filter_by(target_image_id=self.connector.target_image_id) == 1:
                        seed = session.query(Input).filter_by(obj.object_id).one()
                        self.seed_callback(seed)
                session.close()

    def get_seeds(self, inp=None, tags=[], offset=0, size=50, page_no=None):
        if not self.slacrs_instance:
            return

        if self.query_thread and self.query_thread.is_alive():
            self.query_thread.kill_query()

        self.query_signal.querySignal.emit(True)
        self.query_thread = SeedQueryThread(self.slacrs_instance, inp, tags, offset, size, page_no, self.seed_callback)
        self.query_thread.setDaemon(True)
        self.query_thread.start()
