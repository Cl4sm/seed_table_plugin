from PySide2.QtGui import QColor

_l = logging.getLogger(__name__)
# _l.setLevel('DEBUG')

from typing import Dict
from collections import defaultdict

try:
    from slacrs import Slacrs
    from slacrs.model import Input
except ImportError as ex:
    Slacrs = None

class SeedTable:
    """
    Multiple POIs
    """

    def __init__(self, workspace):
        self.workspace = workspace

    def get_all_seeds(self):
        seed_dict = defaultdict(list)
        connector = self.workspace.plugins.get_plugin_instance_by_name("ChessConnector")

        if connector is None:
            # chess connector does not exist
            return None

        slacrs_instance = connector.slacrs_instance()
        if slacrs_instance is None:
            # slacrs does not exist. continue
            return None

        session = slacrs_instance.session()
        if session:
            result = session.query(Input).filter_by(target_image_id=connector.target_image_id).all()
            for seed in result:
                for tag in seed.tags:
                    seed_dict[tag.value].append(seed.value)

            session.close()
        if not seed_dict:
            self.workspace.log("Unable to retrieve seeds for target_image_id: %s" % connector.target_image_id)
        return seed_dict