# brew install python3
# 將 export PATH="$PATH:/Users/irara/Library/Python/3.9/bin" 加入至 ~/.zshrc
# pip3 install pycoingecko matplotlib pandas python-dotenv

# Import 所需套件
import datetime
import pandas as pd
import utils
from datetime import datetime

########################################
#             CoinGecko API            #
########################################

# 設定 coin 名稱及對應 CSV 檔案路徑
coin_csv_file_path = {
    'ethereum': './data/eth_usd_price.csv',
    'bitcoin': './data/btc_usd_price.csv'
}

for coin, csv_file_path in coin_csv_file_path.items():
    # 如果 CSV 檔案不存在，則從 CoinGecko API 取得資料後存入 csv
    if not utils.check_csv_file(csv_file_path):
        coin_price = utils.get_coingecko_price(coin)
        coin_price.to_csv(csv_file_path, index=False)

    # 從 CSV 中取得最後的 Timestamp（含毫秒），並計算與 now 的時間差
    last_timestamp = utils.get_last_time(csv_file_path)
    time_diff = datetime.now() - datetime.fromtimestamp(last_timestamp / 1000.0)
        
    # 如果超過 1 小時，表示 CSV 檔太舊，需將 CSV 檔更新
    if time_diff.total_seconds() > 3600:
        # 從 CoinGecko API 取得資料
        coin_price = utils.get_coingecko_price(coin)
        utils.update_csv(csv_file_path, coin_price)

########################################
#           Tokenlon Subgraph          #
########################################

subgraph_file_path = './data/tokenlon_subgraph.csv'

# 如果 CSV 檔案不存在，則從 Tokenlon Subgraph 取得資料後存入 csv
if not utils.check_csv_file(subgraph_file_path):
    subgraph_data = utils.get_tokenlon_data()
    subgraph_data.to_csv(subgraph_file_path, index=False)

# 從 CSV 中取得最後的 Timestamp（不含毫秒），並計算與 now 的時間差
last_timestamp = utils.get_last_time(subgraph_file_path)
time_diff = datetime.now() - datetime.fromtimestamp(last_timestamp)

# 如果超過 1 小時，表示 CSV 檔太舊，需將 CSV 檔更新
if time_diff.total_seconds() > 3600:
    # 從 Tokenlon Subgraph 取得資料
    subgraph_data = utils.get_tokenlon_data()
    utils.update_csv(subgraph_file_path, subgraph_data)

########################################
#                 Plot                 #
########################################

# 賣 BTC 的賣價
coin = 'bitcoin'
target = 'tether'

# 買 BTC 的買價
# coin = 'tether'
# target = 'bitcoin'

# 賣 ETH 的賣價
coin = 'ethereum'
target = 'tether'

# 買 ETH 的買價
# coin = 'tether'
# target = 'ethereum'


# 設定 coin 的小數點位數
coin_decimals = {
    'tether': 6,
    'ethereum': 18,
    'bitcoin': 8,
}

# 從 Tokenlon Subgraph CSV 取出 subgraph 資料（Timestamp 到秒）
subgraph_data_csv = pd.read_csv(subgraph_file_path, parse_dates=False)
# 將 MakerToken 和 TakerToken 資料全換成小寫，以利後續取出所需的資料
subgraph_data_csv = subgraph_data_csv.assign(MakerToken=subgraph_data_csv['MakerToken'].str.lower(), TakerToken=subgraph_data_csv['TakerToken'].str.lower())

# 從 CoinGecko CSV 取出 ETH-USD 資料（Timestamp 到毫秒）
eth_data_csv = pd.read_csv(coin_csv_file_path['ethereum'], parse_dates=False)
eth_data_csv['Timestamp'] = eth_data_csv['Timestamp'] / 1000

# 從 CoinGecko CSV 取出 BTC-USD 資料（Timestamp 到毫秒）
btc_data_csv = pd.read_csv(coin_csv_file_path['bitcoin'], parse_dates=False)
btc_data_csv['Timestamp'] = btc_data_csv['Timestamp'] / 1000

# ------------------------------

if coin == 'bitcoin' and target == 'tether':
    # 取得所有 Taker 用 WBTC 換 USDT 的資料（賣 BTC 的賣價）
    btc_usdt_condition = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")
    sell_btc = subgraph_data_csv[btc_usdt_condition]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    sell_btc = sell_btc.assign(Price=(sell_btc["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( sell_btc["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    plot_raw_data = utils.add_nearest_price_column(btc_data_csv, sell_btc)

if coin == 'tether' and target == 'bitcoin':
    # 取得所有 Taker 用 WBTC 換 USDT 的資料（買 BTC 的買價）
    usdt_btc_condition = (subgraph_data_csv["MakerToken"] == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    buy_btc = subgraph_data_csv[usdt_btc_condition]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    buy_btc = buy_btc.assign(Price=(buy_btc["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ) /  ( buy_btc["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    plot_raw_data = utils.add_nearest_price_column(btc_data_csv, buy_btc)

if coin == 'ethereum' and target == 'tether':
    # 取得所有 Taker 用 ETH、WETH 換 USDT 的資料（賣 ETH 的賣價）
    eth_usdt_condition_1 = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
    eth_usdt_condition_2 = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0x0000000000000000000000000000000000000000")
    sell_eth = subgraph_data_csv[eth_usdt_condition_1 | eth_usdt_condition_2]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    sell_eth = sell_eth.assign(Price=(sell_eth["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( sell_eth["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    plot_raw_data = utils.add_nearest_price_column(eth_data_csv, sell_eth)

if coin == 'tether' and target == 'ethereum':
    # 取得所有 Taker 用 USDT 換 ETH、WETH 的資料（買 ETH 的買價）
    usdt_eth_condition_1 = (subgraph_data_csv["MakerToken"] == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    usdt_eth_condition_2 = (subgraph_data_csv["MakerToken"] == "0x0000000000000000000000000000000000000000") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    buy_eth = subgraph_data_csv[usdt_eth_condition_1 | usdt_eth_condition_2]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 TakerAmount / MakerAmount 計算的 Price 值
    buy_eth = buy_eth.assign(Price=(buy_eth["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ) /  ( buy_eth["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    plot_raw_data = utils.add_nearest_price_column(eth_data_csv, buy_eth)

if coin == 'bitcoin' and target == 'tether':
    # 取得所有 Taker 用 WBTC 換 USDT 的資料（賣 BTC 的賣價）
    btc_usdt_condition = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599")
    sell_btc = subgraph_data_csv[btc_usdt_condition]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    sell_btc = sell_btc.assign(Price=(sell_btc["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( sell_btc["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    sell_btc = utils.add_nearest_price_column(btc_data_csv, sell_btc)

    # 取得所有 Taker 用 WBTC 換 USDT 的資料（買 BTC 的買價）
    usdt_btc_condition = (subgraph_data_csv["MakerToken"] == "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    buy_btc = subgraph_data_csv[usdt_btc_condition]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    buy_btc = buy_btc.assign(Price=(buy_btc["TakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( buy_btc["MakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    plot_raw_data = utils.add_nearest_price_column(btc_data_csv, buy_btc)
    # 繪製
    utils.plotMove2(f'{coin}-{target}', btc_data_csv, sell_btc, buy_btc)

if coin == 'ethereum' and target == 'tether':
    # 取得所有 Taker 用 ETH、WETH 換 USDT 的資料（賣 ETH 的賣價）
    eth_usdt_condition_1 = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2")
    eth_usdt_condition_2 = (subgraph_data_csv["MakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7") & (subgraph_data_csv["TakerToken"] == "0x0000000000000000000000000000000000000000")
    sell_eth = subgraph_data_csv[eth_usdt_condition_1 | eth_usdt_condition_2]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 MakerAmount / TakerAmount 計算的 Price 值
    sell_eth = sell_eth.assign(Price=(sell_eth["MakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( sell_eth["TakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    sell_eth = utils.add_nearest_price_column(eth_data_csv, sell_eth)
    
    # 取得所有 Taker 用 USDT 換 ETH、WETH 的資料（買 ETH 的買價）
    usdt_eth_condition_1 = (subgraph_data_csv["MakerToken"] == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    usdt_eth_condition_2 = (subgraph_data_csv["MakerToken"] == "0x0000000000000000000000000000000000000000") & (subgraph_data_csv["TakerToken"] == "0xdac17f958d2ee523a2206206994597c13d831ec7")
    buy_eth = subgraph_data_csv[usdt_eth_condition_1 | usdt_eth_condition_2]
    # 在這個 DF 新增一個 Price 欄位，並且儲存用 TakerAmount / MakerAmount 計算的 Price 值
    buy_eth = buy_eth.assign(Price=(buy_eth["TakerAmount"].astype(float) / 10 ** coin_decimals[target] ) /  ( buy_eth["MakerAmount"].astype(float) / 10 ** coin_decimals[coin] ))
    # 在這個 DF 新增一個 CoingeckoPrice 欄位，用來儲存最靠近的市值
    buy_eth = utils.add_nearest_price_column(eth_data_csv, buy_eth)
    # 繪製
    utils.plotMove2(f'{coin}-{target}', eth_data_csv, sell_eth, buy_eth)


# subgraph_data_eth_usdt.to_csv('./test/subgraph_data_eth_usdt.csv', index=False)

# ------------------------------

# plot_data = plot_raw_data[['Timestamp', 'Price', 'CoingeckoPrice']]
# utils.plotMove(f'{coin}-{target}', plot_data)