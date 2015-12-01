#!/usr/bin/env python
from __future__ import print_function
import optparse
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
from six.moves import cPickle
import pickle
import os
import random
import numpy as np
import pandas.io.data as web
import pandas as pd
from datetime import datetime
from keras.models import Sequential, model_from_json
from keras.layers.core import Dense, Activation, Dropout, TimeDistributedDense, Masking
from keras.layers.recurrent import LSTM, SimpleRNN, GRU
from keras.callbacks import EarlyStopping
from utils import load_s_and_p_data, mask_split

def make_RNN(input_shape,layer_dims,layer_type=SimpleRNN,dropout=.2):
    model = Sequential()
    M = Masking(mask_value=0.)
    M._input_shape = input_shape
    model.add(M)
    prev = input_shape[2]
    for layer_dim in layer_dims:
        cur = layer_dim
        model.add(layer_type(input_dim=prev, output_dim=cur, return_sequences=True))
        if dropout:
            model.add(Dropout(dropout))	
        prev=cur		
    model.add(TimeDistributedDense(input_dim=prev, output_dim=input_shape[2]))
    return model

def main():
    p = optparse.OptionParser()
    p.add_option('--load_data', default=False)
    p.add_option('--save_data', default=False)
    p.add_option('--load_model', default=False)
    p.add_option('--run_model', default=True)
    p.add_option('--save_model', default=True)
    p.add_option('--load_results', default=False)
    p.add_option('--save_results', default=False)
    p.add_option('--plot_results', default=True)
    p.add_option('--model_name', default='shallow_RNN',
                 help='Options: shallow_RNN,shallow_LSTM,shallow_GRU,'
                      'deep_RNN, deep_LSTM, deep_GRU')
    p.add_option('--base_path', default="~/machine_learning/stock_sandbox/")
    p.add_option('--dataset', default='jigsaw', help='Options: jigsaw, synthetic, sp500')
    p.add_option('--window', default=100)
    p.add_option('--masked', default=50)
    p.add_option('--patience', default=5)
    p.add_option('--max_epochs', default=1000)
    ops, args = p.parse_args()

    if (not ops.load_results and not ops.run_model) and ops.save_results:
        raise ValueError("Cannot save what has not been loaded or run ")


    if not os.path.exists(os.path.expanduser(ops.base_path+'results')):
        os.makedirs(ops.base_path+'results')
    if not os.path.exists(os.path.expanduser(ops.base_path+'data')):
        os.makedirs(ops.base_path+'data')
    base_name = ops.dataset + '_' + ops.model_name
    data_fname = ops.base_path + 'data/'+ops.dataset + "_data.pkl"
    data_fname = os.path.expanduser(data_fname)
    arch_fname = ops.base_path + 'results/' + base_name + '_model_architecture.json'
    arch_fname = os.path.expanduser(arch_fname)
    weights_fname = ops.base_path + 'results/' + base_name + '_model_weights.h5'
    weights_fname = os.path.expanduser(weights_fname)
    plot_fname = ops.base_path + 'results/' + base_name + '_results.png'
    plot_fname = os.path.expanduser(plot_fname)
    results_fname = ops.base_path + 'results/' + ops.model_name + '_results.pkl'
    results_fname = os.path.expanduser(results_fname)


    #########################BEGIN CODE#######################################
    # tickers = ['AAPL','VZ','NKE','KMI','M','MS','WMT','DOW','MPC']
    tickers = None

    if not ops.load_results:

        if ops.load_data:
            print('Loading data...')
            data = pickle.load(open(data_fname, 'r'))
            if tickers:
                data.loc(tickers)
        else:

            if ops.dataset == "sp500":
                ##### Real Stock Data
                print('Using sp500 data')
                data = load_s_and_p_data(start="2014-1-1", tickers=tickers)
            elif ops.dataset == "synthetic":
                ##### Synthetic data for testing purposes
                print('Using Synthetic data')
                values = 10000
                s = pd.Series(range(values))
                noise = pd.Series(np.random.randn(values))
                s = s / 1000 #+ noise / 100
                d = {'one': s * s * 100/values,
                     'two': np.sin(s * 10.),
                     'three': np.cos(s * 10),
                     'four': np.sin(s * s / 10) * np.sqrt(s) }
                data = pd.DataFrame(d)
            elif ops.dataset == "jigsaw":
                ##### Easy synthetic data for testing purposes
                print('Using jigsaw data')
                flow = (list(range(1, 10, 1)) + list(range(10, 1, -1))) * 1000
                pdata = pd.DataFrame({"a": flow, "b": flow})
                pdata.b = pdata.b.shift(9)
                data = pdata.iloc[10:] * random.random()  # some noise
            else:
                raise ValueError('Not a legal dataset name')

        if ops.save_data:
            print('Saving data...')
            pickle.dump(data, open(data_fname, 'wb+'))

        (X_train, y_train), (X_test, y_test) = mask_split(data, n_prev=ops.window, n_masked=ops.masked)

        if not ops.load_model:
            print('compiling model')
            in_out_neurons = len(data.columns)


            if ops.model_name == "shallow_RNN":
                model = make_RNN(X_train.shape,[300],SimpleRNN,dropout=0)
            elif ops.model_name == "shallow_LSTM":
                model = make_RNN(X_train.shape,[300],LSTM,dropout=0)
            elif ops.model_name == "shallow_GRU":
                model = make_RNN(X_train.shape,[300],GRU,dropout=0)
            elif ops.model_name == "deep_RNN":
                model = make_RNN(X_train.shape,[300,500,200],SimpleRNN,dropout=.2)
            elif ops.model_name == "deep_LSTM":
                model = make_RNN(X_train.shape,[300,500,200],LSTM,dropout=.2)
            elif ops.model_name == "deep_GRU":
                model = make_RNN(X_train.shape,[300,500,200],GRU,dropout=.2)
            else:
                raise ValueError('Not a legal model name')

            model.compile(loss="mean_squared_error", optimizer="rmsprop")
            print('Training model...')
            early_stopping = EarlyStopping(monitor='val_loss', patience=ops.patience, verbose=0)
            model.fit(X_train, y_train, batch_size=450, nb_epoch=ops.max_epochs, validation_split=0.1, callbacks=[early_stopping])
        else:
            print('Loading model...')
            model = model_from_json(open(arch_fname).read())
            model.load_weights(weights_fname)

        if ops.save_model:
            print("Saving model...")
            json_string = model.to_json()
            open(arch_fname, 'w+').write(json_string)
            model.save_weights(weights_fname, overwrite=True)

        if ops.run_model:
            print('Running forecast...')
            #predicted = forecast(model, X_test[0, :, :], n_points=len(X_test))
            predicted = model.predict(X_test)

            rmse = np.sqrt(((predicted - y_test) ** 2).mean(axis=0)).mean()
            print("RMSE:", rmse)

        if ops.save_results:
            print('Saving results...')
            pickle.dump((predicted, y_test), open(results_fname, 'wb+'))
    else:
        print('Loading results...')
        predicted, y_test = pickle.load(open(results_fname, 'r'))

    if ops.plot_results:
        print('Plotting results...')
        fig = plt.figure()
        for i in range(min(4, predicted.shape[2])):
            ax = fig.add_subplot(2, 2, i + 1)
            print(predicted.shape,y_test.shape)
            ax.plot(predicted[0,:,i], color='r')
            ax.plot(y_test[0,:,i], color='b')
            if tickers:
                ax.set_title(tickers[i])

        fig.savefig(plot_fname)


if __name__ == '__main__':
    main()