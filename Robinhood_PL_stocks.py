
from os import path
import robin_stocks.robinhood as rh
import numpy as np
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt

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
    stock_orders_path='./'
    stock_orders_filehead='stock_orders_'
    file_date=dt.datetime.strftime(dt.datetime.now(tz=None),'%b-%d-%Y')
    file_extension='.csv'
    stock_orders_filename=stock_orders_filehead+file_date+file_extension
    return [stock_orders_path, stock_orders_filename]


# Export user transaction data from Robinhood into local filesystem
def create_transactions():
    [csv_path, csv_file] = build_filepath()
    
    if(path.isfile(path.join(csv_path, csv_file))):
        print('Overwriting pre-existing file with updated transaction data.')
    
    rh.export.export_completed_stock_orders(dir_path=csv_path, file_name=csv_file)
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
    outstanding_shares=np.round(df_return['quantity'].cumsum(), decimals=6)
    df_return.insert(loc=6, column='outst_shares', value = outstanding_shares)

    cost_basis_calc=((df_return['quantity']*df_return['average_price']).cumsum()).div(df_return['outst_shares'])
    df_return.insert(loc=8, column='cost_basis', value=cost_basis_calc)

    # clean up the divide-by-zero terms (np.inf) - replace np.inf with NaN for efficient replacement
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
    list_history=rh.get_stock_historicals([ticker],interval='day',span='year')
    df_hist=pd.DataFrame(list_history, dtype=float)
    df_hist.set_index(pd.to_datetime(df_hist['begins_at'])+pd.Timedelta(value=12.75, unit='hours'),inplace=True, drop=True)
    df_hist.insert(loc=5, column='mid_price', value=0.5*(df_hist.open_price+df_hist.close_price))
    df_hist.drop(columns=['session','interpolated'], inplace=True)
    df_hist.index.rename('date',inplace=True)
    df_hist.rename(columns={'symbol':'symbol_hist'}, inplace=True)
    return df_hist
    
# Join the dataframes of Robinhood transactions and Historical asset prices
def join_dataframes(df_hist_data, df_user_trans):

    df_join = df_hist_data.join(df_user_trans, how='outer')
    # Profit / Loss percentage
    df_join.insert(loc=11, column='PL_percentage',value=0.00)
    # Portfolio percentage is currently defined as dollar value of asset x (not a percentage!)
    df_join.insert(loc=12, column='portfolio_percentage', value=float(0.00))
    df_join.drop(columns='symbol_hist', inplace=True)
    df_join['cost_basis'].fillna(method='ffill',inplace=True)
    df_join['mid_price'].fillna(method='ffill',inplace=True)
    df_join['outst_shares'].fillna(method='ffill',inplace=True)
    df_join['cost_basis'].fillna(value=0.0, inplace=True)
    df_join['outst_shares'].fillna(value=0.0, inplace=True)
    
    df_join.loc[df_user_trans.index, 'PL_percentage']=100.*(df_join['average_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    df_join.loc[df_hist_data.index, 'PL_percentage']=100.*(df_join['mid_price']-df_join['cost_basis'])/(df_join['cost_basis'])

    df_join['portfolio_percentage']=(df_join['mid_price']*df_join['outst_shares']).astype(float)

    zero_idx=df_join.index[np.isinf(df_join['PL_percentage'])]
    df_join.loc[zero_idx,'PL_percentage']=0.00
    
    return df_join

# Create mapping between Sectors and randomized RGB tuples for plotting purposes
def construct_sector_dataframe(sym_array):

    df_sector=pd.DataFrame({'sector':[], 'industry':[]})

    for symbol in sym_array: 
        fundamental_data=rh.get_fundamentals([symbol])[0]
        df_sector.loc[symbol, 'sector']  = fundamental_data['sector'] 
        df_sector.loc[symbol, 'industry']= fundamental_data['industry'] 
        df_sector.loc[symbol, 'rgb'] = ''
        
    for u in df_sector.sector.unique():
        idx=df_sector[df_sector.sector == u].index
        color_list=tuple(np.random.choice(range(256), size=3)/256.)
        for sym in idx:
            df_sector.loc[sym,'rgb']=color_list    

    return df_sector
        
# 
def main():

    global df_master_list
    global df_master
    global df_sector    

    call_login()

    create_transactions()

    df_orders = import_transactions()

    # list of dataframe for each asset
    df_master_list = []

    for sym_loop in df_orders.symbol.unique(): 
    
        df_sym = user_transaction_dataframe(sym_loop, df_orders)
    
        df_history = historical_dataframe(sym_loop)

        df_join = join_dataframes(df_history, df_sym)
           
        # create the multi-index levels for each dataframe in df_master_list
        columns_array = [list(np.full(len(df_join.columns),sym_loop)), list(df_join.columns)]
        df_master_list.append(pd.DataFrame(df_join.values, index=df_join.index, columns=columns_array))

    df_master = pd.concat(df_master_list, axis=1, join='outer')
            
    df_sector= construct_sector_dataframe(df_orders.symbol.unique())

    return

#%%
# Basic Matplotlib visualization of Robinhood asset P/L vs time, separated by sector
# Default is to include all sectors in plot, user can specify desired sectors with sector_list arg
def sector_plot_mpl(sector_list=[]):
    
    if sector_list:
        sector_to_plot = sector_list
        # example arg: 
        # sector_list = ['Industrial Services', 'Finance','Technology Services','Electronic Technology']
    else:
        sector_to_plot = df_sector.sector.unique()  # include all sectors

    for df_sym in df_master_list:

        #legend_syms=[]    
        sym_ticker=df_sym.columns[0][0]
        if(df_sector.loc[sym_ticker, 'sector'] in sector_to_plot):

            #legend_syms.append(sym_ticker)
            x_scatter = df_sym.index
            y_scatter = df_sym[sym_ticker]['PL_percentage']
        
            shares_mask=df_sym[sym_ticker]['outst_shares']
        
            scatter_size = df_sym[sym_ticker]['portfolio_percentage'].astype(float)
        
            plt.scatter(x_scatter, y_scatter.mask(shares_mask==0), s=3.0*scatter_size, ec='black', alpha=.75, c=[df_sector.loc[sym_ticker,'rgb']]*len(x_scatter))

            # some hard-coded plot parameters
            plt.ylim(-40,40)
            #plt.legend(loc='upper right', bbox_to_anchor=(1.32, 1.1))
            xmin=pd.to_datetime(dt.datetime(2020, 12, 31, 23, 59, 0))
            xmax=pd.to_datetime(dt.datetime(2021, 8, 1, 0, 1, 0))
            plt.xlim(xmin,xmax)
        

    plt.show()

#%%

if __name__ == '__main__':
    
    main()

#    sec_list = ['Industrial Services', 'Finance','Technology Services','Electronic Technology']
    sec_list=[]
    sector_plot_mpl(sec_list)

