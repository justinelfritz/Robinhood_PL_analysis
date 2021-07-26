
from os import path
import robin_stocks.robinhood as rh
import numpy as np
import pandas as pd
import datetime as dt

#%%

# Robinhood login with or without MFA enabled. Assumes login credentials are
# stored in .creds file in parent directory
def call_login():
    fname_creds = '.creds'
    rpath_creds = './../'
    credspath = path.join(rpath_creds, fname_creds)
    
    if(path.exists(credspath)):
        with open(credspath) as infile:
            lins=infile.readlines()
        uid = lins[0].strip('\n')
        pid = lins[1].strip('\n')
        rh.authentication.login(username=uid, password=pid)
        # Here user is prompted for MFA token if applicable
        
        del uid
        del pid
        del lins
        return True
    else:
        print("Credentials file not found. Check your path.")
        return False

# Construct filepath and filename to import/export Robinhood transaction data
def build_filepath():
    crypto_orders_path='./'
    crypto_orders_filehead='crypto_orders_'
    file_date=dt.datetime.strftime(dt.datetime.now(tz=None),'%b-%d-%Y')
    file_extension='.csv'
    crypto_orders_filename=crypto_orders_filehead+file_date+file_extension
    return [crypto_orders_path, crypto_orders_filename]


# Export user transaction data from Robinhood into local filesystem
def create_transactions():
    [csv_path, csv_file] = build_filepath()
    
    if(path.isfile(path.join(csv_path, csv_file))):
        print('Overwriting pre-existing file with updated transaction data.')
    
    rh.export.export_completed_crypto_orders(dir_path=csv_path, file_name=csv_file)
    return

# Import locally-stored Robinhood transaction data 
def import_transactions():
    [csv_path, csv_file] = build_filepath()    
    
    df_orders=pd.read_csv(path.join(csv_path, csv_file))
    df_orders.sort_values('date',inplace=True)
    df_orders.reset_index(inplace=True, drop=True)   #tz = UTC on data import
    return df_orders


# Data reduction and processing of transaction data
def user_transaction_dataframe(ticker, df_import):
    df_return = df_import[df_import.symbol==ticker].sort_values('date')
    sell_qty=-df_return[df_return.side=='sell'].quantity
    
    # calculate cumulative holding and cost basis
    df_return.loc[sell_qty.index, 'quantity']=sell_qty.values
    outstanding_shares=np.round(df_return['quantity'].cumsum(),decimals=6)
    df_return.insert(loc=6, column='outst_shares', value = outstanding_shares)
    
    cost_basis_calc=((df_return['quantity']*df_return['average_price']).cumsum()).div(df_return['outst_shares'])
    df_return.insert(loc=8, column='cost_basis', value=cost_basis_calc)

    # clean up the divide-by-zero terms (np.inf) - replace np.inf with NaN temporarily
    idx=df_return.index[np.isinf(df_return['cost_basis'])]
    df_return.loc[idx,'cost_basis']=np.nan
    df_return['cost_basis'].fillna(method='ffill', inplace=True)
    idx=df_return[df_return['outst_shares']==0].index
    df_return.loc[idx,'cost_basis']=0.
    
    df_return.drop(columns=['order_type','fees'],inplace=True)
    df_return.set_index(pd.to_datetime(df_return['date'], utc=True),inplace=True)
    df_return.drop(axis=1, columns='date',inplace=True)
    return df_return
    
# Download historical asset price with daily resolution over a specified span (1 year)
def historical_dataframe(ticker):    
    list_history=rh.get_crypto_historicals([ticker.split('USD')[0]],interval='day',span='year')
    df_hist=pd.DataFrame(list_history, dtype=float)
    df_hist.set_index(pd.to_datetime(df_hist['begins_at'])+pd.Timedelta(value=12.75, unit='hours'),inplace=True, drop=True)
    df_hist.insert(loc=5, column='mid_price', value=0.5*(df_hist.open_price+df_hist.close_price))
    df_hist.drop(columns=['begins_at','session','interpolated','symbol','volume'], inplace=True)
    df_hist.index.rename('date',inplace=True)
    return df_hist

# Join the dataframes of Robinhood transactions and Historical asset prices    
def join_dataframes(df_hist_data, df_user_trans):
    
    df_join = df_hist_data.join(df_user_trans, how='outer')
    df_join.insert(loc=11, column='PL_percentage',value=0.00)
    # Portfolio percentage is currently defined as dollar value of asset x (not a percentage!)
    df_join.insert(loc=12, column='portfolio_percentage', value=float(0.00))
    df_join['cost_basis'].fillna(method='ffill',inplace=True)
    df_join['mid_price'].fillna(method='ffill',inplace=True)
    df_join['outst_shares'].fillna(method='ffill',inplace=True)
    df_join['cost_basis'].fillna(value=0.0, inplace=True)
    df_join['outst_shares'].fillna(value=0.0, inplace=True)
    
    df_join.loc[df_user_trans.index, 'PL_percentage']=100.*(df_join['average_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    df_join.loc[df_hist_data.index, 'PL_percentage']=100.*(df_join['mid_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    df_join['portfolio_percentage']=(df_join['mid_price']*df_join['outst_shares']).astype(float)

    zero_idx=df_join.index[np.isinf(df_join['PL_percentage'])]
    df_join.loc[zero_idx,'PL_percentage']=0.0
    
    return df_join

def main():
    
    global df_master_list
    global df_master
    
    call_login()

    create_transactions()

    df_orders = import_transactions()

    df_master_list = []

    for sym_loop in df_orders.symbol.unique(): 
    
        df_sym = user_transaction_dataframe(sym_loop, df_orders)
    
        df_history = historical_dataframe(sym_loop)

        df_join = join_dataframes(df_history, df_sym)
       
    
        columns_array = [list(np.full(len(df_join.columns),sym_loop)), list(df_join.columns)]
        df_master_list.append(pd.DataFrame(df_join.values, index=df_join.index, columns=columns_array))

    df_master=pd.concat(df_master_list, axis=1, join='outer')
    
    return

#%%

if __name__ == '__main__':
    
    main()
    
    
    
    
    
    
    

