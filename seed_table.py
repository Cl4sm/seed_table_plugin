import asyncio
import multiprocessing
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
        self.query_proc = None


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

        self.seed_callback(self.get_seeds())

        prev_target = self.connector.target_image_id
        while not self.should_exit:
            if self.connector.target_image_id != prev_target:
                prev_target = self.connector.target_image_id
                self.seed_callback(self.get_seeds())

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

    def get_seeds(self, inp=None, tags=[], offset=0, size=50):
        if not self.slacrs_instance:
            return

        session = self.slacrs_instance.session()
        self.query_signal.querySignal.emit(True)
        seeds: List[Seed] = []
        if session:
            query = session.query(Input)

            if inp:
                if isinstance(session.bind.dialect, postgresql.dialect):
                    query = query.filter(func.POSITION(literal(inp).op('in')(Input.value)) != 0)
                elif isinstance(session.bind.dialect, sqlite.dialect):
                    pass

            if tags:
                query = query.join(Input.tags)
                for tag in tags:
                    query = query.filter(Input.tags.any(InputTag.value == tag))

            result = query.order_by(Input.created_at).limit(size).offset(offset)
            seeds = [Seed(seed, idx) for idx, seed in enumerate(result)]
            session.close()
            self.seed_callback(seeds)
            self.is_querying = False