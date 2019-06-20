#! /usr/bin/env python
# -*- coding: utf-8 -*-
# vim:fenc=utf-8
#
# Copyright © 2019 David Lilien <dlilien90@gmail.com>
#
# Distributed under terms of the GNU GPL3.0 license.


class PickParameters():
    """Some information used for determining for picks

    This object contains several things that you need to know in order to pick a radar layer, like the frequency of layers you are looking for or the size window in which to search
    
    Attributes
    ----------
    apickthresh: float
        Some kind of auto picking threshold that I have not yet used (default 10)
    freq: float
        Frequency of the layer pick (default 4)
    dt: float
        Time between acquisitions
    plength: float
        Some function of dt and freq
    FWW: float
        Some function of dt and freq
    scst: float
        Some function of plength and FWW
    pol: int
        Polarity of the picks
    apickflag: int
        I think this just kept track of whether StoDeep was autopicking
    addpicktype: str
        Some flag
    radardata: `RadarData`
        A link back up to the RadarData object with which this is affiliated
    """
    attrs = ['apickthresh', 'freq', 'dt', 'plength', 'FWW', 'scst', 'pol', 'apickflag', 'addpicktype']

    def __init__(self, radardata, pickparams_struct=None):
        if pickparams_struct is not None:
            for attr in self.attrs:
                setattr(self, attr, pickparams_struct[0][0][attr][0][0][0][0])
        else:
            self.apickthresh = 10
            self.freq = 4
            self.dt = radardata.dt
            self.plength = 2 * int(round(1. / (self.freq * 1.0e6 * self.dt)))
            self.FWW = int(round(0.66 * (1. / (self.freq * 1.0e6 * self.dt))))
            self.scst = int(round((self.plength - self.FWW) / 2))
            if self.plength < 3:
                print('Warning: high frequency compared to sampling rate means we are forcing a minimum plength')
                self.plength = 3
            if self.FWW == 0:
                self.FWW = 1
            if self.scst == 0:
                self.scst = 0
            self.pol = 1
            self.apickflag = 1
            self.addpicktype = 'zero'
        self.radardata = radardata

    def freq_update(self, freq):
        """Update the frequency at which we are looking

        This is more complicated than just setting freq because other variables are a function of frequency and if not updated will break.

        Parameters
        ----------
        freq: float
            Target pick frequency.
        """
        self.freq = freq
        self.plength = 2 * int(round(1. / (self.freq * 1.0e6 * self.radardata.dt)))
        self.FWW = int(round(0.66 * (1. / (self.freq * 1.0e6 * self.radardata.dt))))
        self.scst = int(round((self.plength - self.FWW) / 2))
        if self.plength < 3:
            print('Warning: high frequency compared to sampling rate means we are forcing a minimum plength')
            self.plength = 3
        if self.FWW == 0:
            self.FWW = 1
        if self.scst == 0:
            self.scst = 0

    def to_struct(self):
        mat = {}
        for attr in self.attrs:
            if getattr(self, attr) is not None:
                mat[attr] = getattr(self, attr)
            else:
                mat[attr] = 0
        return mat
