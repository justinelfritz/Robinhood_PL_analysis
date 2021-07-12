#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jul 11 15:25:16 2021

@author: justing
"""

import robin_stocks.robinhood as rh
import numpy as np
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt

#%%

with open("./../creds_tok.pem") as infile:
    lins=infile.readlines()
uid = lins[0].strip('\n')
pid = lins[1].strip('\n')
rh.login(uid, pid)

#%%

del uid
del pid
del lins

#%%
# check if file/path already exists
#export_orders=rh.export.export_completed_crypto_orders('./')

df_orders=pd.read_csv('./crypto_orders_Jul-11-2021.csv')
df_orders.sort_values('date',inplace=True)
df_orders.reset_index(inplace=True, drop=True)   #tz = UTC on data import

#%%

df_plotter=pd.DataFrame()

for sym_loop in ['ETHUSD','BTCUSD']:#df_orders.symbol:
    print(sym_loop)
    
    df_sub_test = df_orders[df_orders.symbol==sym_loop].sort_values('date')
    df_sub_test.reset_index(inplace=True,drop=True)
    test_col=-df_sub_test[df_sub_test.side=='sell'].quantity
    df_sub_test.loc[test_col.index, 'quantity']=test_col.values
    df_sub_test.insert(loc=6, column='outst_shares', value = np.round(df_sub_test['quantity'].cumsum(),decimals=6))
    cost_basis_calc=((df_sub_test['quantity']*df_sub_test['average_price']).cumsum()).div(df_sub_test['outst_shares'])
    df_sub_test.insert(loc=8, column='cost_basis', value=cost_basis_calc)

    idx=df_sub_test.index[np.isinf(df_sub_test['cost_basis'])]
    df_sub_test.loc[idx,'cost_basis']=np.nan
    df_sub_test['cost_basis'].fillna(method='ffill', inplace=True)

    df_sub_test.drop(axis=1, columns=['order_type','fees'],inplace=True)
    df_sub_test.set_index(pd.to_datetime(df_sub_test['date'], utc=True),inplace=True,drop=True)
    df_sub_test.drop(axis=1, columns='date',inplace=True)


    list_history=rh.get_crypto_historicals([sym_loop.split('USD')[0]],interval='day',span='year')
    df_history=pd.DataFrame(list_history, dtype=float)
    df_history.set_index(pd.to_datetime(df_history['begins_at'])+pd.Timedelta(value=12.75, unit='hours'),inplace=True, drop=True)
    df_history.insert(loc=5, column='mid_price', value=0.5*(df_history.open_price+df_history.close_price))
    df_history.drop(columns=['begins_at'],axis=1,inplace=True)
    df_history.drop(columns=['session','interpolated'], inplace=True)
    df_history.index.rename('date',inplace=True)
    df_history.rename(columns={'symbol':'symbol_hist'},inplace=True)

    df_final = df_history.join(df_sub_test, how='outer')

#df_final.fillna(method='ffill',inplace=True)
    df_final.insert(loc=13, column='PL_percentage',value=0.00)
    df_final.drop(axis=1,columns='symbol_hist',inplace=True)
    df_final['cost_basis'].fillna(method='ffill',inplace=True)
    df_final['mid_price'].fillna(method='ffill',inplace=True)
    df_final['cost_basis'].fillna(value=0.0, inplace=True)
    
# where SIDE != NaN (i.e. SIDE=BUY|SELL)
    idx_bs_events=df_sub_test.index
    df_final.loc[idx_bs_events, 'PL_percentage']=100.*(df_final['average_price']-df_final['cost_basis'])/(df_final['cost_basis'])

# where SIDE = NaN 
    idx_mkt_hist=df_history.index
    df_final.loc[idx_mkt_hist, 'PL_percentage']=100.*(df_final['mid_price']-df_final['cost_basis'])/(df_final['cost_basis'])

    zero_idx=df_final.index[np.isinf(df_final['PL_percentage'])]
    df_final.loc[zero_idx,'PL_percentage']=0.0
    
#    df_plotter.append(df_final['PL_percentage'])
#    df_plotter=pd.concat([df_plotter,df_final['PL_percentage']],axis=1,names=sym_loop)


#for sym_loop in df_orders.symbol:
#    print(sym_loop)
    df_temp=df_final[df_final['symbol']==sym_loop]
    plt.scatter(df_temp.index.values, df_temp.PL_percentage.values, ec='black', s=1e4*df_temp.outst_shares,alpha=0.8)
    plt.plot(df_temp.index.values, df_temp.PL_percentage.values, linestyle='-', color=(0.2,0.2,0.2))
    plt.ylim(-40,140)
#    plt.xlim(df_final.index.values[121],df_final.index.values[-1])
    xmin=pd.to_datetime(dt.datetime(2021, 2, 28, 23, 59, 0))
    xmax=pd.to_datetime(dt.datetime(2021, 9, 1, 0, 1, 0))
    plt.plot([xmin,xmax],[0.,0.],color='black',linestyle='--')
    plt.xlim(xmin,xmax)

plt.show()



#list_test=rh.get_crypto_historicals(['LTC'],interval='day',span='year')


x='LTCUSD'.split('USD')[0]









