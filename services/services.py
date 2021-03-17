from repository import repository
from configuration import logger
from collections import Counter
from datetime import datetime


def create_tweet(tweet):
    id = repository.create_tweet(tweet)
    return id

def retrieve_tweets(last_datetime, tos_date):
    tweets = repository.retrieve_tweets(last_datetime)
    ticker_list = []
    for count, tweet in enumerate(tweets):
        if tweet['create_at'] > tos_date:
            tos_date = tweet['create_at']
        ticker_list.extend(tweet['tickers'])
    graph_data = Counter(ticker_list)
    # logger.info(graph_data)
    return tos_date, graph_data


def add_chart_data(graph_data, new_row):
    for ticker in new_row['tickers']:
        if ticker in graph_data.keys():
            graph_data[ticker] = graph_data[ticker] + 1
        else:
            graph_data[ticker] = 1
    return graph_data

def retrieve_highest_price(ticker):
    highest_price = repository.retrieve_highest_price(ticker)
    try:
        high_price = highest_price[0]['high_price']
    except:
        high_price = ''
    return high_price

def create_highest_price(high_price_dict):
    highest_price = repository.create_highest_price(high_price_dict)
    high_price = highest_price[0]['high_price']
    return high_price

def update_highest_price(high_price_dict):
    repository.update_highest_price(high_price_dict)



