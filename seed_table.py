import asyncio
import threading

from time import sleep
from typing import Dict, List
from tornado.platform.asyncio import AnyThreadEventLoopPolicy

try:
    from slacrs import Slacrs
    from slacrs.model import Input
except ImportError as ex:
    Slacrs = None

class Seed:

    def __init__(self, seed: Input):
        self.created_at = seed.created_at
        self.tags = [x.value for x in seed.tags]
        self.value = seed.value


class SeedTable:
    """
    Multiple POIs
    """

    def __init__(self, workspace, seed_callback=None):
        self.workspace = workspace
        self.seed_callback = seed_callback
        self.connector = None
        self.slacrs_instance = None
        self.should_exit = False

        self.init_instance()

        self.slacrs_thread = threading.Thread(target=self.listen_for_events)
        self.slacrs_thread.setDaemon(True)
        self.slacrs_thread.start()


    def init_instance(self):
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

        self.seed_callback(self.get_all_seeds())

        while not self.should_exit:
            new_event_count = self.slacrs_instance.fetch_events()
            for _ in range(new_event_count):
                e = self.slacrs_instance.event_queue.get_nowait()
                session = self.slacrs_instance.session()
                obj = e.get_object(session)
                if isinstance(obj, Input) and obj.target_image_id == self.connector.target_image_id:
                    seed = Seed(obj)
                    self.seed_callback(seed)

    def get_all_seeds(self):
        session = self.slacrs_instance.session()
        seeds: List[Seed] = []
        if session:
            result = session.query(Input).filter_by(target_image_id=self.connector.target_image_id).all()
            seeds = sorted([Seed(x) for x in result], key=lambda x: x.created_at)
            session.close()
        if len(seeds) == 0:
            self.workspace.log("Unable to retrieve seeds for target_image_id: %s" % connector.target_image_id)

        return seeds