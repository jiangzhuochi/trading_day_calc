# python .\script\get_source_data.py

import akshare as ak

# https://www.akshare.xyz/zh_CN/latest/data/tool/tool.html
# 交易日历
# 接口: tool_trade_date_hist_sina
# 目标地址: https://finance.sina.com.cn/realstock/company/klc_td_sh.txt
# 描述: 获取新浪财经的股票交易日历数据
source_df = ak.tool_trade_date_hist_sina()
num = len(source_df)
trade_date_str = str(source_df.iloc[:, 0].to_list())
tds = (
    '# Automatic generation.\n'
    '# These dates are the opening dates of the Chinese stock market\n'
    '# from December 19, 1990 to December 31, 2021.\n'
    f'# {num} days in total.\n\n'
    'import datetime\n\n'
    f'TRADE_DATE = {trade_date_str}'
)
with open('src/trading_day_calc/trade_date.txt',
          mode='w', encoding='utf8') as f:
    f.write(tds)
