from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler
from bokeh.plotting import figure, ColumnDataSource
from bokeh.layouts import grid, row, column
from bokeh.io import curdoc
from bokeh.palettes import d3

import pymodbus.client.sync

import datetime
import numpy as np

def make_document(doc):

    def update():

        # get time stamp
        sample_time = datetime.datetime.now()
        # TODO: how do we update the data source with an array of voltages?
        # voltages = client.read_holding_registers(0, 16, unit=0xAA).registers[2:]
        # for now, make separate calls
        v = {}
        for i in cells:
            address = i + 1
            v[i] = client.read_holding_registers(address, 4, unit=0xAA).registers[0]/10

        # get balance state and encode colors
        balance = client.read_holding_registers(51, 16, unit=0xAA).registers[0]
        balances = '{:016b}'.format(balance)

        # get pack current and temp
        current = np.array(client.read_holding_registers(38, 2, unit=0xAA).registers, dtype=np.uint16).view(dtype=np.float32)[0]
        temperature = client.read_holding_registers(48, 2, unit=0xAA).registers[0]/10.

        # update trend source
        new = {}
        new.update({'v{}'.format(i):[v[i]] for i in cells})
        new.update({'c{}'.format(i):[palette[i-1]] for i in cells})
        new.update({'s{}'.format(i):[4] if balances[num_cells - i]=='1' else [0] for i in cells})
        new['x'] = [sample_time]
        trend_source.stream(new)

        temp_source.stream({'x':[sample_time], 't':[temperature]})

        # update bar source
        bar_source.data['c'] = [palette[i-1] for i in cells]
        bar_source.data['v'] = [v[i] for i in cells]

        # write to log file
        with open(log_file, 'a') as f:
            f.write(sample_time.strftime('%Y-%m-%dT%H:%M:%S'))
            f.write(', ')
            for i in cells:
                f.write('{}, '.format(v[i]))
            f.write('{}, '.format(balances[:-2]))
            f.write('{}, '.format(temperature))
            f.write('{}, '.format(current))
            f.write('\n')

    # create data stores
    num_cells = 14
    cells = list(range(1, num_cells + 1))

    # create colors for battery cell rows
    palette = d3['Category20'][14]

    trend_dict = {}
    trend_dict.update({'v{}'.format(i):[] for i in cells})
    trend_dict.update({'c{}'.format(i):[] for i in cells})
    trend_dict.update({'s{}'.format(i):[] for i in cells})
    trend_dict['x'] = []
    trend_source = ColumnDataSource(trend_dict)

    bar_source = ColumnDataSource({'x': cells, 'v': [], 'c':[]})
    temp_source = ColumnDataSource({'x':[], 't':[]})

    # set up graphs and callback
    doc.add_periodic_callback(update, 5000)

    # define figures and layout
    bar_fig = figure(title='Cell Voltages', y_range=[3000, 4200])
    trend_fig = figure(title='Cell Voltages Trend', x_axis_type='datetime')
    temp_fig = figure(title='Temperature', x_axis_type='datetime')

    # generate trend lines and data points
    for i in cells:
        voltage = 'v{}'.format(i)
        color = 'c{}'.format(i)
        size = 's{}'.format(i)
        trend_fig.circle(source=trend_source, x='x', y=voltage, color=color, size=size)
        trend_fig.line(source=trend_source, x='x', y=voltage, color=palette[i-1])

    bar_fig.vbar(source=bar_source, x='x', top='v', color='c', width=0.9)
    temp_fig.line(source=temp_source, x='x', y='t', color='black')

    plots = grid(row(column(trend_fig, temp_fig), bar_fig), sizing_mode='stretch_both')
    doc.add_root(plots)
    doc.title = "Energus BMS Real-Time Voltages"

bluetooth_port = '/dev/tty.EPSBMS-SPPDev'
usb_port = '/dev/tty.SLAB_USBtoUART'
port = usb_port
client = pymodbus.client.sync.ModbusSerialClient(method='rtu',
         port=port, timeout=2, baudrate=115200)
client.connect()

log_file = datetime.datetime.now().strftime('%Y-%m-%d-%H%M%S') + '-log.csv'

make_document(curdoc())
