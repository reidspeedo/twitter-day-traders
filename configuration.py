import logging.config
import os

log_file_path = "/Users/reidrelatores/PycharmProjects/twitter-day-traders/logfile.log"

try:
    os.remove(log_file_path)
except:
    print('No log file to delete')

logging.config.fileConfig(fname='file.conf', disable_existing_loggers=False)
logger = logging.getLogger('logger')

my_twitterid = '1369887486810353664'