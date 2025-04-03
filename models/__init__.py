"""
Models package for the application.
"""

from models.data_module.watra_kod import WatraKod
from models.data_module.celky import Celky
from models.config_module.plant import Plant
from models.config_module.shuttle import Shuttle
from models.config_module.travel_time import TravelTime
from models.config_module.celky_shuttle import CelkyShuttle
from models.schedule import Schedule
from models.data_module.sap_data import SAPData
from models.rcmpsp.rcmpsp_result import RcmpspResult

from models.data_module.sap_strategy import (
    SAPStrategy,
    TANUMTPOSNormalizedStrategy,
    TANUMTPOSSlashStrategy,
    LEStrategy,
    MATNRStrategy,
    StrategyFactory,
    SAPDataProcessor
)
from models.data_module.data_module import (
    get_watra_data,
    aggregate_data,
    analyze_transport_statistics,
    run_analysis
)

from models.db import (
    init_db,
    import_excel_to_db,
    get_config_data,
    get_all_watra_kody,
    get_watra_kod,
    add_watra_kod,
    update_watra_kod,
    delete_watra_kod,
    get_filtered_config_data
)

# Initialize database when models are imported
WatraKod.init_db()
Celky.init_db()
Plant.init_db()
Shuttle.init_db()
TravelTime.init_db()
CelkyShuttle.init_db()
Schedule.init_db()
RcmpspResult.init_db()
