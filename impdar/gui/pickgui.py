#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2018 David Lilien <dlilien90@gmail.com>
#
# Distributed under terms of the GNU GPL3.0 license.

import sys
from .ui import RawPickGUI
from ..lib import plot, RadarData, picklib
import numpy as np
import os.path
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.figure import Figure
from PyQt5 import QtCore, QtWidgets, QtGui
from matplotlib.backends.qt_compat import is_pyqt5
if is_pyqt5():
    from matplotlib.backends.backend_qt5agg import (FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
    from PyQt5.QtWidgets import QFileDialog, QMessageBox, QDialog
else:
    from matplotlib.backends.backend_qt4agg import (FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
    from PyQt4.QtWidgets import QFileDialog, QMessageBox, QDialog

symbols_for_cps = ['o', 'd', 's']


def pick(radardata, guard_save=True, xd=False, yd=False):
    if xd:
        x = 'dist'
    else:
        x = 'tracenum'
    if yd:
        y = 'depth'
    else:
        y = 'twtt'

    if not hasattr(radardata, 'picks') or radardata.picks is None:
        radardata.picks = RadarData.Picks(radardata)

    app = QtWidgets.QApplication(sys.argv)
    ip = InteractivePicker(radardata, xdat=x, ydat=y)
    ip.show()
    sys.exit(app.exec_())


class InteractivePicker(QtWidgets.QMainWindow, RawPickGUI.Ui_MainWindow):

    def __init__(self, dat, xdat='tracenum', ydat='twtt', x_range=(0, -1), guard_save=False):
        # Next line is required for Qt, then give us the layout
        super(InteractivePicker, self).__init__()
        self.setupUi(self)
        self.FigCanvasWidget.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.FigCanvasWidget.canvas.setFocus()

        # Connect the menu to actions
        # save menu
        self.actionSave_pick.triggered.connect(self._save_as)
        self.actionSave_as.triggered.connect(self._save_as)
        self.actionClose.triggered.connect(self.close)

        #pick menu
        self.actionLoad_crossprofile.triggered.connect(self._load_cp)

        # Process menu
        self.actionAdaptive_Horizontal_filter.triggered.connect(self._ahfilt)
        self.actionVertical_band_pass.triggered.connect(self._vbp)
        self.actionReverse.triggered.connect(self._reverse)
        self.actionCrop.triggered.connect(self._crop)

        # Connect controls on the left
        self.ColorSelector.currentTextChanged.connect(self._color_select)

        # Easy access to normal mpl figure and axes
        self.ax = self.FigCanvasWidget.canvas.ax
        self.fig = self.FigCanvasWidget.canvas.fig
        plt.ion()

        # Two constants to keep track of how to prompt for saves
        self.fn = None
        self._saved = True

        # Set defaults
        self.bwb = 'bwb'
        self.freq = 4
        self.pick_mode = 'select'

        # line is the matplotlib object of the current pick
        self.cline = []
        self.tline = []
        self.bline = []

        # pick_pts contains our picked points, which will differ from what we want to save in the file. Need to have one per line.
        self.pick_pts = []
        self.dat = dat
        self.current_pick = None

        # For loading cross profiles, we want to use multiple symbols
        self.cp = 0

        if self.dat.picks is not None and self.dat.picks.samp1 is not None:
            self.pick_pts = [p[~np.isnan(p)].tolist() for p in self.dat.picks.samp1]

        try:
            if xdat not in ['tracenum', 'dist']:
                raise ValueError('x axis choices are tracenum or dist')
            if ydat not in ['twtt', 'depth']:
                raise ValueError('y axis choices are twtt or depth')

            if x_range is None:
                self.x_range = (0, -1)
            if x_range[-1] == -1:
                self.x_range = (x_range[0], self.dat.tnum)

            self.lims = np.percentile(dat.data[:, self.x_range[0]:self.x_range[-1]], (10, 90))
            self.clims = [self.lims[0] * 2 if self.lims[0] < 0 else self.lims[0] / 2, self.lims[1] * 2]
            self.minSpinner.setValue(self.lims[0])
            self.maxSpinner.setValue(self.lims[1])
            self.FrequencySpin.setValue(self.dat.picks.pickparams.freq)
            if hasattr(dat.flags, 'elev') and dat.flags.elev:
                yd = dat.elevation
                self.ax.set_ylabel('Elevation (m)')
                self.y = 'depth'
            else:
                self.ax.invert_yaxis()
                if ydat == 'twtt':
                    self.yd = dat.travel_time
                    self.ax.set_ylabel('Two way travel time (usec)')
                    self.y = 'twtt'
                elif ydat == 'depth':
                    if dat.nmo_depth is not None:
                        self.yd = dat.nmo_depth
                        self.y = 'nmo_depth'
                    else:
                        self.yd = dat.travel_time / 2.0 * 1.69e8 * 1.0e-6
                        self.y = 'depth'
                    self.ax.set_ylabel('Depth (m)')

            if xdat == 'tracenum':
                self.xd = np.arange(int(self.dat.tnum))[self.x_range[0]:self.x_range[-1]]
                self.ax.set_xlabel('Trace number')
            elif xdat == 'dist':
                self.xd = self.dat.dist[self.x_range[0]:self.x_range[-1]]
                self.ax.set_xlabel('Distance (km)')

            self.im = self.ax.imshow(dat.data[:, self.x_range[0]:self.x_range[-1]], cmap=plt.cm.gray, vmin=self.lims[0], vmax=self.lims[1], extent=[np.min(self.xd), np.max(self.xd), np.max(self.yd), np.min(self.yd)], aspect='auto')
            if self.dat.picks.samp1 is not None:
                self.cline = [None for i in range(self.dat.picks.samp1.shape[0])]
                self.bline = [None for i in range(self.dat.picks.samp1.shape[0])]
                self.tline = [None for i in range(self.dat.picks.samp1.shape[0])]
                for i in range(self.dat.picks.samp1.shape[0]):
                    if i == self.dat.picks.samp1.shape[0] - 1:
                        colors = 'gmm'
                    else:
                        colors = 'byy'
                    self.current_pick = np.vstack((self.dat.picks.samp1[i, :], self.dat.picks.samp2[i, :], self.dat.picks.samp3[i, :], self.dat.picks.time[i, :], self.dat.picks.power[i, :]))
                    self._pick_ind = i
                    self.pickNumberBox.setValue(self.dat.picks.picknums[i])
                    self.update_lines(colors=colors, picker=5)

            self.kpid = self.fig.canvas.mpl_connect('key_press_event', self._press)
            self.krid = self.fig.canvas.mpl_connect('key_release_event', self._release)
            self.bpid = self.fig.canvas.mpl_connect('pick_event', self._click)
            # We need this so we no if we are nanpicking
            self._n_pressed = False

            #####
            # Connect some stuff after things are set up
            # Do this here so we don't unintentionally trigger things that are not initialized
            #####
            self.minSpinner.valueChanged.connect(self._lim_update)
            self.maxSpinner.valueChanged.connect(self._lim_update)
            self.FrequencySpin.valueChanged.connect(self._freq_update)
            self.modeButton.clicked.connect(self._mode_update)
            self.newpickButton.clicked.connect(self._add_pick)
            self.pickNumberBox.valueChanged.connect(self._pickNumberUpdate)

            plt.show(self.fig)
        except KeyboardInterrupt:
            plt.close('all')

    #######
    # Handling of the bar of option things on the left
    #######
    def _color_select(self, val):
        self.im.set_cmap(plt.cm.get_cmap(val))
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def _lim_update(self, val):
        if self.maxSpinner.value() < self.minSpinner.value():
            self.maxSpinner.setValue(self.minSpinner.value() + 1)
        self.im.set_clim(vmin=self.minSpinner.value(), vmax=self.maxSpinner.value())
        self.lims[0] = self.minSpinner.value()
        self.lims[1] = self.maxSpinner.value()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def _freq_update(self, val):
        self.dat.picks.pickparams.freq_update(val)
        self.freq = val

    def _pickNumberUpdate(self, val):
        # Do not use picks that already exist
        if self.dat.picks is not None and self.dat.picks.picknums is not None:
            if val not in self.dat.picks.picknums:
                self.dat.picks.picknums[self._pick_ind] = val
            elif self.dat.picks.picknums[self._pick_ind] == val:
                pass
            else:
                self.pickNumberBox.setValue(val + 1)

    def _mode_update(self):
        _translate = QtCore.QCoreApplication.translate
        if self.pick_mode == 'select':
            self.modeButton.setText(_translate('MainWindow', 'Edit Mode'))
            self.FigCanvasWidget.setCursor(QtGui.QCursor(QtCore.Qt.CrossCursor))
            self.pick_mode = 'edit'
            self.fig.canvas.mpl_disconnect(self.bpid)
            self.bpid = self.fig.canvas.mpl_connect('button_press_event', self._click)
            for c, b, t in zip(self.cline, self.bline, self.tline):
                if c is not None:
                    c.set_picker(None)
                    b.set_picker(None)
                    t.set_picker(None)
        else:
            self.modeButton.setText(_translate('MainWindow', 'Select Mode'))
            self.FigCanvasWidget.setCursor(QtGui.QCursor(QtCore.Qt.ArrowCursor))
            self.pick_mode = 'select'
            self.fig.canvas.mpl_disconnect(self.bpid)
            self.bpid = self.fig.canvas.mpl_connect('pick_event', self._click)
            for c, b, t in zip(self.cline, self.bline, self.tline):
                if c is not None:
                    c.set_picker(5)
                    b.set_picker(5)
                    t.set_picker(5)

    #######
    # Handling of mouse events
    #######
    def _click(self, event):
        # This will handle both edit mode and select mode clicks
        if self.FigCanvasWidget.mpl_toolbar._active is not None:
            return
        if self.pick_mode == 'edit':
            self._edit_lines_click(event)
        elif self.pick_mode == 'select':
            self._select_lines_click(event)

    def _edit_lines_click(self, event):
        """We have a click on the canvas while in edit mode. We need to shunt this event to the appropriate function

        Can be plain left click (pick)
        left click with n depressed (nanpick)
        or right click (delete)
        """
        tnum, snum = np.argmin(np.abs(self.xd - event.xdata)), np.argmin(np.abs(self.yd - event.ydata))
        if len(self.cline) == 0:
            self._add_pick(snum=snum, tnum=tnum)
        else:
            if event.button == 1:
                if self._n_pressed:
                    self._add_nanpick(snum, tnum)
                else:
                    self._add_point_pick(snum, tnum)
            elif event.button == 3:
                self._delete_picks(snum, tnum)

        self.update_lines()
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        self._saved = False

    def _add_point_pick(self, snum, tnum):
        """We are given a snum, tnum location in the image: follow layer to that point, plot it"""
        picks = picklib.pick(self.dat.data[:, self.dat.picks.lasttrace.tnum[self._pick_ind]:tnum], self.dat.picks.lasttrace.snum[self._pick_ind], snum, pickparams=self.dat.picks.pickparams)
        self.current_pick[:, self.dat.picks.lasttrace.tnum[self._pick_ind]:tnum] = picks
        self.dat.picks.update_pick(self.dat.picks.picknums[self._pick_ind], self.current_pick)
        self.dat.picks.lasttrace.tnum[self._pick_ind] = tnum
        self.dat.picks.lasttrace.snum[self._pick_ind] = snum

    def _add_nanpick(self, snum, tnum):
        """Update for a nanpick. This is trivial, since the matrix is already NaNs"""
        # Just move our counter over so we know where to go next
        self.dat.picks.lasttrace.tnum[self._pick_ind] = tnum
        self.dat.picks.lasttrace.snum[self._pick_ind] = snum

    def _delete_picks(self, snum, tnum):
        self.current_pick[:, tnum:] = np.nan

    def update_lines(self, colors='gmm', picker=None):
        """Update the plotting of the current pick.
        
        Parameters
        ----------
        colors: str
            3-letter string of one-letter colors
        picker:
            argument to pass to plot of cline (if new) for selection tolerance (use if plotting in select mode)
        """
        c = np.zeros(self.xd.shape)
        c[:] = np.nan
        c[~np.isnan(self.current_pick[1, :])] = self.yd[self.current_pick[1, :][~np.isnan(self.current_pick[1, :])].astype(int)]
        t = np.zeros(self.xd.shape)
        t[:] = np.nan
        t[~np.isnan(self.current_pick[0, :])] = self.yd[self.current_pick[0, :][~np.isnan(self.current_pick[0, :])].astype(int)]
        b = np.zeros(self.xd.shape)
        b[:] = np.nan
        b[~np.isnan(self.current_pick[2, :])] = self.yd[self.current_pick[2, :][~np.isnan(self.current_pick[2, :])].astype(int)]
        if self.cline[self._pick_ind] is None:
            self.cline[self._pick_ind], = self.ax.plot(self.xd, c, color=colors[0], picker=picker)
            self.tline[self._pick_ind], = self.ax.plot(self.xd, t, color=colors[1])
            self.bline[self._pick_ind], = self.ax.plot(self.xd, b, color=colors[2])
        else:
            # This is a little complicated to avoid plotting NaN regions
            self.cline[self._pick_ind].set_data(self.xd, c)
            self.tline[self._pick_ind].set_data(self.xd, t)
            self.bline[self._pick_ind].set_data(self.xd, b)

    def _dat_to_snumtnum(self, x, y):
        if self.xscale == 'tnum':
            xo = int(x)
        else:
            xo = np.argmin(np.abs(self.dat.dist - x))

        yo = np.argmin(np.abs(getattr(self.dat, self.yscale) - y))
        return xo, yo

    def _select_lines_click(self, event):
        thisline = event.artist
        if thisline in self.cline:
            self._pick_ind = self.cline.index(thisline)
            for i, (c, b, t) in enumerate(zip(self.cline, self.bline, self.tline)):
                if i == self._pick_ind:
                    c.set_color('g')
                    b.set_color('m')
                    t.set_color('m')
                else:
                    c.set_color('b')
                    b.set_color('y')
                    t.set_color('y')

        self.pickNumberBox.setValue(self.dat.picks.picknums[self._pick_ind])

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    #######
    # Logistics of saving and closing
    #######
    def closeEvent(self, event):
        if not self._saved:
            self._save_cancel_close(event)
        else:
            event.accept()

    def _save_cancel_close(self, event):
        dialog = QMessageBox()
        dialog.setStandardButtons(QMessageBox.Save | QMessageBox.Close | QMessageBox.Cancel)
        result = dialog.exec()
        if result == QMessageBox.Cancel:
            event.ignore()
        elif result == QMessageBox.Close:
            event.accept()
        else:
            if self.fn is None:
                if not self._save_as(event):
                    event.ignore() 
                else:
                    event.accept()
            else:
                self._save()
                event.accept()

    def _save_inplace(self, evt):
        """Save the file without changing name"""
        self_save_fn(self.dat.fn)

    def _save_pick(self, evt):
        """Save with _pick appended"""
        self._save_fn(self.dat.fn[:-4] + '_pick.mat')

    def _save_as(self, event=None):
        """Fancy file handler for gracious exit"""
        fn, test = QFileDialog.getSaveFileName(self, "QFileDialog.getSaveFileName()", self.dat.fn, "All Files (*);;mat Files (*.mat)")
        if fn:
            self._save_fn(fn)
        return fn

    def _save_fn(self, fn):
        self.fn = fn
        self.dat.save(fn)
        self._saved = True
        self.actionSave_pick.triggered.disconnect()
        self.actionSave_pick.triggered.connect(self._save_as)

    def _load_cp(self, event=None):
        """Load a cross profile"""
        fn, test = QFileDialog.getOpenFileName(self, "QFileDialog.getSaveFileName()", self.dat.fn, "All Files (*);;mat Files (*.mat)")
        if fn:
            dat_cross = RadarData.RadarData(fn)
            try:
                out_tnums, out_snums = picklib.get_intersection(self.dat, dat_cross)
            except AttributeError:
                warn('No picks', 'There are no picks in the crossprofile for us to load')
                return

            # Check if we are in depth or time space
            if self.y == 'twtt':
                y_coords_plot = dat_cross.travel_time
            elif self.y in ['depth', 'nmo_depth']:
                if dat_cross.nmo_depth is not None:
                    y_coords_plot = dat_cross.nmo_depth
                else:
                    y_coords_plot = dat_cross.travel_time / 2.0 * 1.69e8 * 1.0e-6
            
            for tnum, snum, pn in zip(out_tnums, out_snums, dat_cross.picks.picknums):
                yv = y_coords_plot[snum]
                self.ax.plot([tnum], [yv], linestyle='none', marker=symbols_for_cps[self.cp], color='k', markersize=10)
                self.ax.text(tnum, yv, str(pn), color='w', ha='center', va='center', fontsize=8)

            self.cp += 1
            self.fig.canvas.draw()
            self.fig.canvas.flush_events()

    ######
    # Decorators for processing
    ######
    def update_radardata(self):
        """Make the plot reflect updates to the data"""
        self.im.set_data(self.dat.data[:, self.x_range[0]:self.x_range[-1]])
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
        self._saved = False

    def _ahfilt(self, event):
        self.progressLabel.setText('Horizontally filtering...')
        self.progressBar.setProperty("value", 25)
        QtWidgets.QApplication.processEvents()
        self.dat.adaptivefilt()
        self.progressBar.setProperty("value", 75)
        QtWidgets.QApplication.processEvents()
        self.update_radardata()
        self.progressLabel.setText('Done...')
        self.progressBar.setProperty("value", 100)

    def _vbp(self, event):
        dialog = VBPInputDialog()
        result = dialog.exec()
        if result != 0:
            self.progressLabel.setText('Vertically Bandpassing...')
            self.progressBar.setProperty("value", 25)
            QtWidgets.QApplication.processEvents()
            self.dat.vertical_band_pass(*dialog.lims)
            self.progressBar.setProperty("value", 75)
            QtWidgets.QApplication.processEvents()
            self.update_radardata()
            self.progressLabel.setText('Done...')
            self.progressBar.setProperty("value", 100)

    def _reverse(self, event):
        self.dat.reverse()
        self.update_radardata()

    def _crop(self, event):
        dialog = CropInputDialog()
        result = dialog.exec()
        if result != 0:
            self.progressLabel.setText('Cropping...')
            self.progressBar.setProperty("value", 25)
            QtWidgets.QApplication.processEvents()
            self.dat.crop(dialog.val, dimension=dialpickNumberBox.og.inputtype, top_or_bottom=dialog.top_or_bottom)
            self.progressBar.setProperty("value", 75)
            QtWidgets.QApplication.processEvents()
            self.update_radardata()
            self.progressLabel.setText('Done...')
            self.progressBar.setProperty("value", 100)

    #######
    # Enable the key presses from the old stointerpret
    #######
    def _press(self, event):
        if event.key == 'd':
            self.press_f()
        elif event.key == ' ':
            self.press_space()
        elif event.key == 'n':
            self._n_pressed = True

    def _release(self, event):
        if event.key == 'n':
            self._n_pressed = False

    def _add_pick(self, tnum=None, snum=None):
        # Give the user a visual clue to what is being picked by using different colors for the old lines
        # I think that c, b, t should always be the same length, if this doesnt work I think it means there is a deeper bug
        for cl, bl, tl in zip(self.cline, self.bline, self.tline):
            if cl is not None:
                cl.set_color('b')
                bl.set_color('y')
                tl.set_color('y')
                self.fig.canvas.draw()
                self.fig.canvas.flush_events()

        self.cline.append(None)
        self.bline.append(None)
        self.tline.append(None)
        pickNum = self.pickNumberBox.value() + 1
        newp = False
        while not newp:
            try:
                pick_ind = self.dat.picks.add_pick(pickNum)
                self._pick_ind = pick_ind - 1
                self.pickNumberBox.setValue(pickNum)
                newp = True
            except ValueError:
                pickNum += 1
        d = np.zeros((5, self.dat.tnum))
        d[d == 0] = np.nan
        self.current_pick = d
        if snum is not None:
            if tnum is None:
                tnum = 0
            self.current_pick[:, tnum] = picklib.packet_pick(self.dat.data[:, tnum], self.dat.picks.pickparams, snum)
            self.dat.picks.lasttrace.tnum[self._pick_ind] = tnum
            self.dat.picks.lasttrace.snum[self._pick_ind] = snum


class VBPInputDialog(QDialog):
    def __init__(self, parent=None):
        super(VBPInputDialog, self).__init__(parent)
        layout = QtWidgets.QFormLayout()
        self.minlabel = QtWidgets.QLabel()
        self.minlabel.setText('Min (MHz):')
        self.minspin = QtWidgets.QSpinBox()
        self.minspin.setMinimum(0.)
        self.minspin.setMaximum(999999.)
        self.minspin.setValue(50.)
        self.maxlabel = QtWidgets.QLabel()
        self.maxlabel.setText('Max (MHz):')
        self.maxspin = QtWidgets.QSpinBox()
        self.maxspin.setMinimum(0.)
        self.maxspin.setMaximum(999999.)
        self.maxspin.setValue(250.)
        layout.addRow(self.minlabel, self.minspin)
        layout.addRow(self.maxlabel, self.maxspin)
        self.cancel = QtWidgets.QPushButton("Cancel")
        self.ok = QtWidgets.QPushButton("Ok")(dat_cross.picks.picknums)
        layout.addRow(self.cancel, self.ok)
        self.ok.clicked.connect(self.clickOK)
        self.cancel.clicked.connect(self.close)
        self.setLayout(layout)
        self.setWindowTitle("Vertical Bandpass")

    def clickOK(self):
        if self.minspin.value() >= self.maxspin.value():
            self.minspin.setValue(self.maxspin.value() - 1)
            return
        self.lims = (self.minspin.value(), self.maxspin.value())
        self.accept()

    def __init__(self, parent=None):
        super(CropInputDialog, self).__init__(parent)
        layout = QtWidgets.QFormLayout()

        self.spinnerlabel = QtWidgets.QLabel()
        self.spinnerlabel.setText('Cutoff in TWTT (usec):')
        self.spinner = QtWidgets.QDoubleSpinBox()
        self.spinner.setMinimum(0)
        self.spinner.setMaximum(10000)
        self.spinner.setDecimals(4)
        layout.addRow(self.spinnerlabel, self.spinner)

        self.inputlabel = QtWidgets.QLabel()
        self.inputlabel.setText('Input units:')
        self.inputtype = QtWidgets.QComboBox()
        self.inputtype.addItem('twtt')
        self.inputtype.addItem('snum')
        self.inputtype.addItem('depth')
        self.inputtype.currentTextChanged.connect(self._type_select)
        layout.addRow(self.inputlabel, self.inputtype)

        self.tblabel = QtWidgets.QLabel()
        self.tblabel.setText('Crop off:')
        self.tb = QtWidgets.QComboBox()
        self.tb.addItem('top')
        self.tb.addItem('bottom')
        layout.addRow(self.tblabel, self.tb)

        self.cancel = QtWidgets.QPushButton("Cancel")
        self.ok = QtWidgets.QPushButton("Ok")
        layout.addRow(self.cancel, self.ok)
        self.ok.clicked.connect(self.clickOK)
        self.cancel.clicked.connect(self.close)
        self.setLayout(layout)
        self.setWindowTitle('Vertically crop')

    def clickOK(self):
        self.val = self.spinner.value()
        self.inputtype = self.inputtype.currentText()
        self.top_or_bottom = self.tb.currentText()
        self.accept()

    def _type_select(self, val):
        if val == 'snum':
            self.spinnerlabel.setText('Cutoff (sample num):')
            self.spinner.setDecimals(0)
        if val == 'twtt':
            self.spinnerlabel.setText('Cutoff in TWTT (usec):')
            self.spinner.setDecimals(3)
        if val == 'depth':
            self.spinnerlabel.setText('Cutoff in depth (m):')
            self.spinner.setDecimals(2)


def warn(message, long_message):
    msg = QtWidgets.QMessageBox()
    msg.setIcon(QtWidgets.QMessageBox.Warning)

    msg.setText(message)
    msg.setInformativeText(long_message)
    msg.setWindowTitle(message)
    msg.setStandardButtons(QMessageBox.Ok)
    return msg.exec_()


# We want to add this fancy colormap
colorb = [(1.0000, 1.0000, 1.000),
          (0.9984, 1.0000, 0.2000),
          (1.0000, 0.6792, 0.6500),
          (0.5407, 0.9000, 0.5400),
          (0.7831, 0.8950, 0.8950),
          (1.0000, 1.0000, 1.0000),
          (0.3507, 0.3500, 0.7000),
          (0.1740, 0.5800, 0.5800),
          (0.0581, 0.5800, 0.0580),
          (0.4792, 0.4800, 0.0600),
          (0.8000, 0., 0.),
          (0., 0., 0.)]

percents = np.array([0, 63, 95, 114, 123, 127, 130, 134, 143, 162, 194, 256])
percents = percents / 256.

plt.cm.register_cmap(name='CEGSIC', cmap=colors.LinearSegmentedColormap.from_list('CEGSIC', list(zip(percents, colorb))))
