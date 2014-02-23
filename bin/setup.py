from datetime import datetime
import sys

import pandas as pd
from matplotlib import pyplot as plt

from tsdb.database import TSDB

print("")
if len(sys.argv) != 2:
    print("Require a tsdb database to be specified.\n\nUsage:\n\ttsdb TSDB_PATH")
else:
    db = TSDB(sys.argv[1])
    print("Running timeseries database: {0}".format(db))
    print("Access the 'db' object to operate on the database.")
