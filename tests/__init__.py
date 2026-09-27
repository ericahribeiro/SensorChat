import logging

logging.getLogger("sensorchat").addHandler(logging.NullHandler())
logging.getLogger("sensorchat").propagate = False
