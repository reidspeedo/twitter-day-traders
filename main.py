import tweepy
import logging.config
import os
import pandas as pd
from collections import Counter

from services import services

log_file_path = "/Users/reidrelatores/PycharmProjects/twitter-day-traders/logfile.log"

try:
    os.remove(log_file_path)
except:
    print('No log file to delete')

logging.config.fileConfig(fname='file.conf', disable_existing_loggers=False)
logger = logging.getLogger('logger')

my_twitterid = '1369887486810353664'

def create_api():
    consumer_key = os.getenv("TWITTER_CONSUMER_KEY")
    consumer_secret = os.getenv("TWITTER_CONSUMER_SECRET")
    access_token = os.getenv("TWITTER_ACCESS_TOKEN")
    access_token_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)
    api = tweepy.API(auth)

    try:
        api.verify_credentials()
        logger.error("authentication success")
    except Exception as e:
        logger.error("Error creating API", exc_info=True)
        raise e
    logger.info("API created")
    return api

def filter_extract_tickers(tweet):
    unique_tickers = []
    if '$' in tweet.text:
        split_tweet = tweet.text.split()
        tickers = split_tweet.copy()
        for word in split_tweet:
            if '$' not in word:
                tickers.remove(word)
            elif any(char.isdigit() for char in word):
                tickers.remove(word)
            elif not any(char.isalpha() for char in word):
                tickers.remove(word)
            else:
                pass

        unique_tickers = []
        for i in tickers:
            if i.upper() not in unique_tickers:
                unique_tickers.append(i.upper())

        if len(unique_tickers) > 0:
            include_tweet = True
        else:
            include_tweet = False

    else:
        logging.info(f'No ticker found in tweet: {tweet.id}')
        include_tweet = False

    return tweet, include_tweet, unique_tickers


def create_row_for_data_frame(tweet, tickers):
    df_new_row = \
        {
            'tweet_id': tweet.id_str,
            'create_at': tweet.created_at,
            'user_id': tweet.user.id_str,
            'user_name': tweet.user.screen_name,
            'tweet_text': tweet.text,
            'tickers': tickers
        }
    logger.info(df_new_row)
    return df_new_row

class FavRetweetListener(tweepy.StreamListener):
    def __init__(self, api, initial_df, graph_data):
        self.api = api
        self.me = api.me()
        self.df = initial_df
        self.graph_data = graph_data

    def on_status(self, tweet):
        clean_tweet, include_tweet, tickers = filter_extract_tickers(tweet)
        if include_tweet:
            new_row = create_row_for_data_frame(tweet, tickers)
            self.df = self.df.append(new_row, ignore_index=True)
            self.graph_data = add_chart_data(self.graph_data, new_row)
            plot_chart(self.graph_data)

    def on_error(self, status):
        logger.error(status)

def retrieve_timeline(api):
    tweets = api.home_timeline()
    df = pd.DataFrame()
    for tweet in tweets:
        clean_tweet, include_tweet, tickers = filter_extract_tickers(tweet)
        if include_tweet:
            new_row = create_row_for_data_frame(clean_tweet, tickers)
            df = df.append(new_row, ignore_index=True)
    return df

def create_chart_data(dataframe):
    ticker_list = []
    for row in dataframe['tickers']:
        ticker_list.extend(row)
    graph_data = Counter(ticker_list)
    return graph_data

def add_chart_data(graph_data, new_row):
    for ticker in new_row['tickers']:
        if ticker in graph_data.keys():
            graph_data[ticker] = graph_data[ticker] + 1
        else:
            graph_data[ticker] = 1
    return graph_data

def plot_chart(graph_data):
    stock_symbols = []
    mentions = []
    for key, value in graph_data.items():
        stock_symbols.append(key)
        mentions.append(value)

    data_formatted = {
        'Stock Symbol': stock_symbols,
        'Mentions': mentions
    }
    data_set = pd.DataFrame(data_formatted)
    logging.info(data_set)

def main(my_twitterid = '1369887486810353664'):
    api = create_api()

    friends = [my_twitterid]
    for follower in api.friends():
        friends.append(str(follower.id))
    logging.info(f'Friend IDs {friends}')

    initial_df = retrieve_timeline(api)
    graph_data = create_chart_data(initial_df)
    plot_chart(graph_data)

    tweets_listener = FavRetweetListener(api, initial_df, graph_data)
    stream = tweepy.Stream(api.auth, tweets_listener)
    stream.filter(follow=friends)
    return api

if __name__ == '__main__':
    api = main()





