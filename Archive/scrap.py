import pymongo
import os
import datetime
from collections import Counter

connection_string = os.environ.get("MONGO_DB_CONN_STR")
client = pymongo.MongoClient(connection_string)
db = client.twitter

def retrieve_tweets(last_datetime):
    tweets = db.tweet.find({'create_at': {"$gt": last_datetime}})
    return tweets

start_date = datetime.datetime.today().date()
midnight = datetime.datetime.combine(start_date, datetime.time(0, 0))
all_tweets = retrieve_tweets(midnight)

UPST_TIME = []
lists_now = []

for tweets in all_tweets:
    UPST_TIME.extend(tweets['tickers'])

graph_data = Counter(UPST_TIME)

#print(graph_data)
for key in graph_data.keys():
    if key not in lists_now:
        lists_now.append(key)

print(graph_data)
print(lists_now)
print(len(lists_now))
