import pymongo
import os
import datetime
from configuration import logger
from pytz import timezone

connection_string = os.environ.get("MONGO_DB_CONN_STR")
client = pymongo.MongoClient(connection_string)
db = client.twitter

def retrieve_tweets(last_datetime):
    tweets = db.tweet.find({'create_at': {"$gt": last_datetime.isoformat()}})
    return tweets

start_date = datetime.datetime.today().date()
midnight = datetime.datetime.combine(start_date, datetime.time(0, 0))
all_tweets = retrieve_tweets(midnight)

UPST_TIME = []
UPST_TWEET_ID = []
for tweet in all_tweets:
     print(tweet['create_at'].astimezone(timezone('US/Pacific')))
#     for symbol in tweet['tickers']:
#         # print(symbol)
#         if symbol == '$UPST':
#             print(tweet['created_at'])
# #             UPST_TIME.append(tweet['create_at'].time().strftime('%H:%M'))
# #             UPST_TWEET_ID.append(tweet['tweet_id'])
# #
# print(UPST_TIME)
# print(UPST_TWEET_ID)
# print(len(UPST_TWEET_ID))
