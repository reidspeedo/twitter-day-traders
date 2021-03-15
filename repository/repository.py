import pymongo
import os
from configuration import logger

connection_string = os.environ.get("MONGO_DB_CONN_STR")
client = pymongo.MongoClient(connection_string)
db = client.twitter

def create_tweet(tweet):
    id = db.tweet.insert(tweet)
    logger.info(tweet['tickers'])
    return id

def retrieve_tweets(last_datetime):
    tweets = db.tweet.find({'create_at': {"$gt": last_datetime}})
    return tweets


