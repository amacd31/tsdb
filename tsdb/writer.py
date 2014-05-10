import calendar
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import numpy as np
import os
import pandas as pd
from struct import pack, unpack, calcsize

from .constants import MISSING_VALUE, METADATA_MISSING_VALUE
from .log_handler import LogHandler

field_names = ['date', 'value', 'metaID']
entry_format = 'ldi' # long, double, int; See field names above.
entry_size = calcsize(entry_format)

def __pack(record_date, value, default_flag=0):

    if np.isnan(value):
        data = pack('ldi',
                    record_date,
                    MISSING_VALUE,
                    METADATA_MISSING_VALUE)
    else:
        data = pack('ldi', record_date, value, default_flag)

    return data

def __convert_and_validate(ts):
    """
        Turn tuple of (dates, values) into a pandas TimeSeries.

        Validates the input is sensible (e.g. consecutive values).

        :param ts: Tuple of (dates, values)
        :type ts: (np.ndarray, np.ndarray)
    """
    # Convert all to datetime when utctimetuple is not available (i.e. date object).
    for i in range(0, len(ts[0])):
        if 'utctimetuple' not in dir(ts[0][i]):
            ts[0][i] = dt.fromordinal(ts[0][i].toordinal())

    cur_date = ts[0][0]
    for the_date in ts[0][1:]:
        if cur_date >= the_date:
            raise ValueError('Unordered dates were supplied. {0} >= {1}'. \
                    format(cur_date, the_date))
        cur_date = the_date

    series = pd.TimeSeries(ts[1], index=ts[0]).asfreq('D')

    assert (series.index[-1] - series.index[0]).days + 1 == len(series.values)

    return series

def bulk_write(tsdb_file, x):
    """
        Good for initial bulk load. Expects continuous time series.
    """
    series = __convert_and_validate(x)

    with open(tsdb_file, 'wb') as writer:
        for date, value in zip(series.index, series.values):
            # Convert to datetime when utctimetuple is not available (i.e. date object).
            if 'utctimetuple' not in dir(date):
                date = dt.fromordinal(date.toordinal())
            datestamp = calendar.timegm(date.utctimetuple())
            data = __pack(datestamp, value)
            writer.write(data)

def write(tsdb_file, ts):
    """
        Smart write. Expects continuous time series.

        Will only update existing values where they have changed.
        Changed existing values are returned in a list.
    """

    series = __convert_and_validate(ts)

    start_date = series.index[0]
    end_date = series.index[-1]


    with open(tsdb_file, 'rb') as reader:
        first_record = unpack(entry_format, reader.read(entry_size))
        reader.seek(entry_size * -1, os.SEEK_END)
        last_record = unpack(entry_format, reader.read(entry_size))

    first_record_date = dt.utcfromtimestamp(first_record[0])
    last_record_date = dt.utcfromtimestamp(last_record[0])
    modified_entries = []

    offset = (start_date - first_record_date).days

    # We are updating existing data
    if start_date <= last_record_date:
        with open(tsdb_file, 'r+b') as writer:
            existing_records = []

            # Read existing overlapping data for comparisons
            writer.seek(entry_size * offset, os.SEEK_SET)

            for record in iter(lambda: writer.read(entry_size), ""):
                if not record: break
                existing_records.append(unpack(entry_format, record))

            records_length = len(existing_records)

            # Start a count for records from the starting write position
            rec_count = 0
            writer.seek(entry_size * offset, os.SEEK_SET)
            for date, value in zip(series.index, series.values):
                datestamp = calendar.timegm(date.utctimetuple())
                overlapping = rec_count <= records_length - 1
                if overlapping and existing_records[rec_count][1] == value:
                    # Skip writing the entry if it hasn't changed.
                    writer.seek(entry_size * (rec_count +1) + (entry_size * offset), os.SEEK_SET)
                elif overlapping and existing_records[rec_count][1] != value:
                    modified_entries.append(existing_records[rec_count])
                    data = __pack(datestamp, value)
                    writer.write(data)
                else:
                    data = __pack(datestamp, value)
                    writer.write(data)
                rec_count += 1

    # We are appending data
    elif start_date > last_record_date:
        with open(tsdb_file, 'a+b') as writer:
            delta_days = (start_date - last_record_date).days
            if delta_days > 0:
                for day in range(1, delta_days):
                    the_date = last_record_date + relativedelta(days=day)
                    data = pack('ldi',
                                calendar.timegm(the_date.utctimetuple()),
                                                MISSING_VALUE,
                                                METADATA_MISSING_VALUE)
                    writer.write(data)
            for date, value in zip(series.index, series.values):
                datestamp = calendar.timegm(date.utctimetuple())
                data = __pack(datestamp, value)
                writer.write(data)
    else: # Not yet supported
        raise NotImplementedError

    return modified_entries

def write_log(log_file, modified, replacement_datetime):

    if not os.path.exists(log_file):
        with LogHandler(log_file, 'w') as writer:
            writer.create_skeleton()

    with LogHandler(log_file, 'a') as writer:
        writer.write(modified, calendar.timegm(replacement_datetime.utctimetuple()))
