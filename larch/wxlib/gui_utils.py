#!/usr/bin/env python

import sys
import wx
try:
    from wx._core import PyDeadObjectError
except:
    PyDeadObjectError = Exception

import time
import os
import locale

from ..larchlib import ensuremod
from .larchfilling import Filling
from ..utils import get_cwd

DEF_CHOICES = [('All Files', '*.*')]

class LarchWxApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    """wrapper for wx apps, with the following arguments and features:

    _larch (None or Interpreter):   instance of Larch Interpreter [None]
    version_info (None or string):  larch version to check for updates [None]
    with_inspect (bool):            use wx inspection tool for debugging [False]
    with_c_locale (bool):           whether to force C locale [True]

    """
    def __init__(self, _larch=None, version_info=None, with_inspect=False,
                 with_c_locale=True, **kws):
        self._larch = _larch
        self.version_info = version_info
        self.with_inspect = with_inspect
        self.with_c_locale = with_c_locale
        wx.App.__init__(self, **kws)

    def OnInit(self):
        self.createApp()
        if self.with_inspect:
            self.ShowInspectionTool()
        return True

    def createApp(self):
        return True

    def InitLocale(self):
        """over-ride wxPython default initial locale"""
        if self.with_c_locale:
            self._initial_locale = None
            locale.setlocale(locale.LC_ALL, 'C')
        else:
            lang, enc = locale.getdefaultlocale()
            self._initial_locale = wx.Locale(lang, lang[:2], lang)
            locale.setlocale(locale.LC_ALL, lang)

    def run(self):
        self.MainLoop()


def SafeWxCall(fcn):
    """decorator to wrap function in a wx.CallAfter() so that
    calls can be made in a separate thread, and asynchronously.
    """
    def wrapper(*args, **kwargs):
        "callafter wrapper"
        try:
            wx.CallAfter(fcn, *args, **kwargs)
        except PyDeadObjectError:
            pass
    wrapper.__doc__ = fcn.__doc__
    wrapper.__name__ = fcn.__name__
    wrapper.__dict__.update(fcn.__dict__)
    return wrapper

def panel_pack(window, panel, pad=10):
    """
    a simple method to pack a single panel to a single frame
    """
    sizer = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(panel, 1, wx.LEFT, 5)
    window.SetSizer(sizer)
    sizer.Fit(window)
    w0, h0 = window.GetSize()
    w1, h1 = window.GetBestSize()
    window.SetSize((max(w0, w1)+pad, max(h0, h1)+pad))

def show_wxsizes(obj):
    """recursively show sizes of wxPython objects --
    useful for avoiding size<1 errors"""
    for child in obj.GetChildren():
        try:
            csize = child.GetSize()
            if csize[0] < 1 or csize[1] < 1:
                print(child, csize)
        except:
            pass
        try:
            show_wxsizes(child)
        except:
            pass

def wx_update(_larch=None, **kws):
    """force an update of wxPython windows"""
    symtable = ensuremod(_larch, '_sys')
    symtable = ensuremod(_larch, '_sys.wx')
    input_handler = symtable.get_symbol('_sys.wx.inputhook') ##.input_handler
    wxping = symtable.get_symbol('_sys.wx.ping')
    if input_handler is not None:
        symtable.set_symbol("_sys.wx.force_wxupdate", True)
        wxping(0.002)

class wxLarchTimer(wx.MiniFrame):
   """hidden wx frame that contains only a timer widget.
   This timer widget will periodically force a wx update
   """
   def __init__(self, parent, _larch, polltime=50):
       wx.MiniFrame.__init__(self, parent, -1, '')
       self.Show(False)
       self.polltime = polltime
       self.timer = wx.Timer(self)
       self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
       self.symtable = _larch.symtable
       self.wxping =self.symtable.get_symbol('_sys.wx.ping')

   def Start(self, polltime = None):
       if polltime is None: polltime = self.polltime
       if polltime is None: polltime = 500
       self.timer.Start(polltime)

   def Stop(self):
       self.wxping(0.005)
       self.symtable.set_symbol("_sys.wx.force_wxupdate", True)
       self.timer.Stop()
       self.Destroy()

   def OnTimer(self, event=None):
       """timer events -- here we execute any un-executed shell code"""
       self.symtable.set_symbol('_sys.wx.force_wxupdate', True)
       self.wxping(0.001)
       time.sleep(0.001)
       print(" ..")

# @SafeWxCall
def gcd(wxparent=None, _larch=None, **kws):
    """Directory Browser to Change Directory"""
    parent = _larch.symtable.get_symbol('_sys.wx.wxapp')
    if parent is None:
        _larch.raise_exception(None, msg='wx not supported')

    dlg = wx.DirDialog(None, 'Choose Directory',
                       defaultPath = get_cwd(),
                       style = wx.DD_DEFAULT_STYLE)

    if dlg.ShowModal() == wx.ID_OK:
        os.chdir(dlg.GetPath())
    dlg.Destroy()
    return get_cwd()


class DataBrowserFrame(wx.Frame):
    """Frame containing the Filling for Data browser."""
    name = 'Filling Frame'
    def __init__(self, parent=None, id=-1, title='Larch Data Tree',
                 pos=wx.DefaultPosition, size=(650, 450),
                 style=wx.DEFAULT_FRAME_STYLE, _larch=None):
        """Create FillingFrame instance."""
        wx.Frame.__init__(self, parent, id, title, pos, size, style)
        self.CreateStatusBar()
        self.SetStatusText('')

        self.filling = Filling(parent=self, rootObject=_larch.symtable,
                               rootLabel='_main', rootIsNamespace=False,
                               static=False)

        self.filling.tree.setStatusText = self.SetStatusText
        self.filling.tree.display()
        self.root = self.filling.tree.GetRootItem()
        self.filling.tree.Expand(self.root)
        self.Show()
        self.Raise()

    def redraw(self):
        self.filling.tree.Collapse(self.root)
        self.filling.tree.Expand(self.root)

def databrowser(_larch=None, **kws):
    """show DataBrowser window for exploring Larch Groups and Data"""
    parent = _larch.symtable.get_symbol('_sys.wx.wxapp')
    if parent is None:
        _larch.raise_exception(None, msg='wx not supported')
    return DataBrowserFrame(parent=parent, _larch=_larch)


# @SafeWxCall
def fileprompt(mode='open', multi=True, message = None,
                fname=None, choices=None, _larch=None, **kws):
    """show File Browser for opening or saving file.
    Returns name of selected file.

    options:
       mode:     one of 'open' or 'save'
       fname:    default filename
       message:  text to display in top window bar
       multi:    whether multiple files are allowed [True]
       choices:  list of (title, fileglob) to restrict choices

    > x = fileprompt(choices=(('All Files', '*.*'), ('Python Files', '*.py')))

    """
    symtable = ensuremod(_larch)

    if fname is None:
        fname = ''
        try:
            fname = symtable.get_symbol("_sys.wx.default_filename")
        except:
            pass
    symtable.set_symbol("_sys.wx.default_filename", fname)

    if choices is None or len(choices) < 1:
        choices = DEF_CHOICES
        try:
            choices = symtable.get_symbol("_sys.wx.ext_choices")
        except:
            pass
    symtable.set_symbol("_sys.wx.ext_choices", choices)

    wildcard = []
    for title, fglob in choices:
        wildcard.append('%s (%s)|%s' % (title, fglob, fglob))
    wildcard = '|'.join(wildcard)

    if mode == 'open':
        style = wx.FD_OPEN|wx.FD_CHANGE_DIR
        if multi:
            style = style|wx.FD_MULTIPLE
        if message is None:
            message = 'Open File '
    else:
        style = wx.FD_SAVE|wx.FD_CHANGE_DIR
        if message is None:
            message = 'Save As '

    #parent.Start()
    parent = _larch.symtable.get_symbol('_sys.wx.wxapp')
    if parent is None:
        _larch.raise_exception(None, msg='wx not supported')
    if hasattr(parent, 'GetTopWindow'):
        parent = parent.GetTopWindow()
    timer = wxLarchTimer(parent, _larch)
    dlg = wx.FileDialog(parent=timer, message=message,
                        defaultDir=get_cwd(),
                        defaultFile=fname,
                        wildcard =wildcard,
                        style=style)
    path = None
    if dlg.ShowModal() == wx.ID_OK:
        path = dlg.GetPaths()
        if len(path) == 1:
            path = path[0]

    dlg.Destroy()
    timer.Destroy()
    return path
