import pymongo
import os
from configuration import logger

connection_string = os.environ.get("MONGO_DB_CONN_STR")
client = pymongo.MongoClient(connection_string)
db = client.twitter

def create_tweet(tweet):
    id = db.tweet.insert(tweet)
    logger.info(id)
    return id

def retrieve_initial_tweets(number_of_tweets):
    tweets = db.tweet.find().sort([('_id', -1)]).limit(number_of_tweets)
    return tweets


