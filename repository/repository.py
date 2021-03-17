import pymongo
import os
from configuration import logger

connection_string = os.environ.get("MONGO_DB_CONN_STR")
client = pymongo.MongoClient(connection_string)
db = client.twitter

def create_tweet(tweet):
    id = db.tweet.insert(tweet)
    logger.info(f"Tweet ID: {tweet['tweet_id']} / Tickers: {tweet['tickers']}")
    return id

def retrieve_tweets(last_datetime):
    tweets = db.tweet.find({'create_at': {"$gt": last_datetime}})
    return tweets

def retrieve_highest_price(ticker):
    highest_price = db.highest_price.find({'ticker': ticker})
    return highest_price

def create_highest_price(high_price_dict):
    highest_price = db.highest_price.insert(high_price_dict)
    return highest_price

def update_highest_price(high_price_dict):
    highest_price = db.highest_price.update_one({'ticker': high_price_dict['ticker']}, {
        '$set': {
            'high_price': high_price_dict['high_price']
        }
    }, upsert=False)
    return highest_price