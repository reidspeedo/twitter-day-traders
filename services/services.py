from repository import repository
from configuration import logger
from collections import Counter

def create_tweet(tweet):
    id = repository.create_tweet(tweet)
    #Add to graph_data
    return id

def retrieve_initial_tweets(number_of_tweets):
    tweets = repository.retrieve_initial_tweets(number_of_tweets)
    ticker_list = []
    for tweet in tweets:
        ticker_list.extend(tweet['tickers'])
    graph_data = Counter(ticker_list)
    logger.info(graph_data)
    return graph_data


def add_chart_data(graph_data, new_row):
    for ticker in new_row['tickers']:
        if ticker in graph_data.keys():
            graph_data[ticker] = graph_data[ticker] + 1
        else:
            graph_data[ticker] = 1
    return graph_data