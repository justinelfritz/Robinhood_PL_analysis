#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 11 15:25:16 2021

@author: justing
"""
from os import path
import robin_stocks.robinhood as rh
import numpy as np
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt

#%%

def call_login():
    fname_creds = 'creds_tok.pem'
    rpath_creds = './../'
    credspath = path.join(rpath_creds, fname_creds)
    
    if(path.exists(credspath)):
        with open(credspath) as infile:
            lins=infile.readlines()
        uid = lins[0].strip('\n')
        pid = lins[1].strip('\n')
        rh.authentication.login(username=uid, password=pid)

        del uid
        del pid
        del lins
        return True
    else:
        print("Credentials file not found. Check your path.")
        return False


def build_filepath():
    crypto_orders_path='./'
    crypto_orders_filehead='crypto_orders_'
    file_date=dt.datetime.strftime(dt.datetime.now(tz=None),'%b-%d-%Y')
    file_extension='.csv'
    crypto_orders_filename=crypto_orders_filehead+file_date+file_extension
    return [crypto_orders_path, crypto_orders_filename]



def create_transactions():
    [csv_path, csv_file] = build_filepath()
    
    print(csv_path)
    print(csv_file)
    
    if(path.isfile(path.join(csv_path, csv_file))):
        print('Overwriting pre-existing file with updated transaction data.')
    
    rh.export.export_completed_crypto_orders(dir_path=csv_path, file_name=csv_file)
    return


def import_transactions():
    [csv_path, csv_file] = build_filepath()    
    
    df_orders=pd.read_csv(path.join(csv_path, csv_file))
    df_orders.sort_values('date',inplace=True)
    df_orders.reset_index(inplace=True, drop=True)   #tz = UTC on data import
    return df_orders


def user_transaction_dataframe(ticker, df_import):
    df_return = df_import[df_import.symbol==ticker].sort_values('date')
    sell_qty=-df_return[df_return.side=='sell'].quantity
    
    # calculate cumulative holding and cost basis
    df_return.loc[sell_qty.index, 'quantity']=sell_qty.values
    df_return.insert(loc=6, column='outst_shares', value = np.round(df_return['quantity'].cumsum(),decimals=6))
    cost_basis_calc=((df_return['quantity']*df_return['average_price']).cumsum()).div(df_return['outst_shares'])
    df_return.insert(loc=8, column='cost_basis', value=cost_basis_calc)

    # clean up the divide-by-zero terms (np.inf) - replace np.inf with NaN temporarily
    idx=df_return.index[np.isinf(df_return['cost_basis'])]
    df_return.loc[idx,'cost_basis']=np.nan
    df_return['cost_basis'].fillna(method='ffill', inplace=True)

    # drop un-needed rows and re-index
    df_return.drop(columns=['order_type','fees'],inplace=True)
    df_return.set_index(pd.to_datetime(df_return['date'], utc=True),inplace=True)
    df_return.drop(axis=1, columns='date',inplace=True)
    return df_return
    

def historical_dataframe(ticker):    
    list_history=rh.get_crypto_historicals([ticker.split('USD')[0]],interval='day',span='year')
    df_hist=pd.DataFrame(list_history, dtype=float)
    df_hist.set_index(pd.to_datetime(df_hist['begins_at'])+pd.Timedelta(value=12.75, unit='hours'),inplace=True, drop=True)
    df_hist.insert(loc=5, column='mid_price', value=0.5*(df_hist.open_price+df_hist.close_price))
    df_hist.drop(columns=['begins_at','session','interpolated','symbol','volume'], inplace=True)
    df_hist.index.rename('date',inplace=True)
    return df_hist
    
def join_dataframes(df_hist_data, df_user_trans):
    df_join = df_hist_data.join(df_user_trans, how='outer')
    df_join.insert(loc=11, column='PL_percentage',value=0.00)
    df_join['cost_basis'].fillna(method='ffill',inplace=True)
    df_join['mid_price'].fillna(method='ffill',inplace=True)
    df_join['cost_basis'].fillna(value=0.0, inplace=True)
    
    # assign PL_percentage where SIDE != NaN (i.e. SIDE=BUY|SELL)
    df_join.loc[df_sym.index, 'PL_percentage']=100.*(df_join['average_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    # assign PL_percentage where SIDE = NaN (during normal historical record)
    df_join.loc[df_history.index, 'PL_percentage']=100.*(df_join['mid_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    zero_idx=df_join.index[np.isinf(df_join['PL_percentage'])]
    df_join.loc[zero_idx,'PL_percentage']=0.0
    
    return df_join


#%%

call_login()

#%%

orders_csv=create_transactions()

df_import_raw = import_transactions()

#%%

df_orders = df_import_raw

iter_count=0
df_multix = []

for sym_loop in df_orders.symbol.unique(): #df_orders.symbol:
    
    
    df_sym = user_transaction_dataframe(sym_loop, df_orders)
    
    df_history = historical_dataframe(sym_loop)

    df_join = join_dataframes(df_history, df_sym)
       
    
    columns_array = [list(np.full(len(df_join.columns),sym_loop)), list(df_join.columns)]
    df_multix.append(pd.DataFrame(df_join.values, index=df_join.index, columns=columns_array))

    iter_count = iter_count + 1

#%%
    
df_full = pd.concat(df_multix, axis=1, join='outer', )
#    elif (iter_count != 0):
#    columns_array = [list(np.full(len(df_join.columns),sym_loop)), list(df_join.columns)]
#    df_append = pd.DataFrame(df_join.values, index=df_join.index, columns=columns_array)
#    df_multix.join(df_append, how='outer', on='date')
        

    
#    plt.scatter(df_temp.index.values, df_temp.PL_percentage.values, ec='black', s=24,alpha=0.8)
#    plt.plot(df_temp.index.values, df_temp.PL_percentage.values, linestyle='-', color=(0.2,0.2,0.2))
#    plt.ylim(-60,160)
#    plt.xlim(df_final.index.values[121],df_final.index.values[-1])
#    xmin=pd.to_datetime(dt.datetime(2021, 1, 31, 23, 59, 0))
#    xmax=pd.to_datetime(dt.datetime(2021, 9, 1, 0, 1, 0))
#    plt.plot([xmin,xmax],[0.,0.],color='black',linestyle='--')
#    plt.xlim(xmin,xmax)

#plt.show()




#%%
#arrays=[np.array(["bar", "bar", "baz", "baz", "foo", "foo", "qux", "qux"]),np.array(["one", "two", "one", "two", "one", "two", "one", "two"]),]

#df_x = pd.DataFrame(np.random.randn(3, 8), index=["A", "B", "C"], columns=arrays)
#    df_multi=pd.DataFrame(df_final, index=, columns=index)
#%%
#vals_array = df_temp.values
#col_array = [list(np.full(len(df_temp.columns),'ETHUSD')), list(df_temp.columns)]
#df_mx = pd.DataFrame(vals_array, index=df_temp.index, columns=col_array)









