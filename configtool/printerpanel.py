
import os
import wx
import re

from configtool.data import (defineValueFormat, defineBoolFormat, reCommDefBL,
                             reCommDefBoolBL, reHelpTextStart, reHelpTextEnd,
                             reDefine, reDefineBL, reDefQS, reDefQSm,
                             reDefQSm2, reDefBool, reDefBoolBL)
from configtool.mechanicalpage import MechanicalPage
from configtool.accelerationpage import AccelerationPage
from configtool.miscellaneouspage import MiscellaneousPage


class PrinterPanel(wx.Panel):
  def __init__(self, parent, nb, folder):
    wx.Panel.__init__(self, nb, wx.ID_ANY)
    self.parent = parent

    self.cfgValues = {}
    self.heaters = []
    self.dir = os.path.join(folder, "config")

    sz = wx.BoxSizer(wx.HORIZONTAL)

    self.nb = wx.Notebook(self, wx.ID_ANY, size = (21, 21),
                          style = wx.BK_DEFAULT)

    self.pages = []
    self.titles = []
    self.pageModified = []
    self.pageValid = []

    self.pgMech = MechanicalPage(self, self.nb, len(self.pages))
    text = "Mechanical"
    self.nb.AddPage(self.pgMech, text)
    self.pages.append(self.pgMech)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgAcc = AccelerationPage(self, self.nb, len(self.pages))
    text = "Acceleration"
    self.nb.AddPage(self.pgAcc, text)
    self.pages.append(self.pgAcc)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgMiscellaneous = MiscellaneousPage(self, self.nb, len(self.pages))
    text = "Miscellaneous"
    self.nb.AddPage(self.pgMiscellaneous, text)
    self.pages.append(self.pgMiscellaneous)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    sz.Add(self.nb, 1, wx.EXPAND + wx.ALL, 5)

    self.SetSizer(sz)

  def onPageChange(self, evt):
    print "printer notebook page changed"
    print evt.GetSelection()
    print evt.GetEventObject()
    evt.Skip()

  def checkFocus(self):
    print "check focus: ", self.nb.GetSelection()

  def assertModified(self, pg, flag = True):
    self.pageModified[pg] = flag
    self.modifyTab(pg)

  def isModified(self):
    return (True in self.pageModified)

  def assertValid(self, pg, flag = True):
    self.pageValid[pg] = flag
    self.modifyTab(pg)

    if False in self.pageValid:
      self.parent.enableSavePrinter(False)
    else:
      self.parent.enableSavePrinter(True)

  def modifyTab(self, pg):
    if self.pageModified[pg] and not self.pageValid[pg]:
      pfx = "?* "
    elif self.pageModified[pg]:
      pfx = "* "
    elif not self.pageValid[pg]:
      pfx = "? "
    else:
      pfx = ""

    self.nb.SetPageText(pg, pfx + self.titles[pg])

  def setHeaters(self, ht):
    return self.pgMiscellaneous.setHeaters(ht)

  def onClose(self, evt):
    if not self.confirmLoseChanges("exit"):
      return

    self.Destroy()

  def confirmLoseChanges(self, msg):
    if True not in self.pageModified:
      return True

    dlg = wx.MessageDialog(self, "Are you sure you want to " + msg + "?\n"
                                 "There are changes to your printer "
                                 "configuration that will be lost.",
                           "Changes pending",
                           wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION)
    rc = dlg.ShowModal()
    dlg.Destroy()

    if rc != wx.ID_YES:
      return False

    return True

  def onLoadConfig(self, evt):
    if not self.confirmLoseChanges("load a new printer configuration"):
      return

    wildcard = "Printer configuration (printer.*.h)|printer.*.h"

    dlg = wx.FileDialog(self, message = "Choose a printer config file",
                        defaultDir = self.dir, defaultFile = "",
                        wildcard = wildcard, style = wx.OPEN | wx.CHANGE_DIR)

    path = None
    if dlg.ShowModal() == wx.ID_OK:
      path = dlg.GetPath()

    dlg.Destroy()
    if path is None:
      return

    self.dir = os.path.dirname(path)
    rc = self.loadConfigFile(path)

    if not rc:
      dlg = wx.MessageDialog(self, "Unable to process file %s." % path,
                             "File error", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return

    self.parent.enableSavePrinter(True)
    self.parent.setPrinterTabText("Printer <%s>" % os.path.basename(path))

    for pg in self.pages:
      pg.insertValues(self.cfgValues)
      pg.setHelpText(self.helpText)

    k = 'DC_EXTRUDER'
    if k in self.cfgValues.keys():
      print "calling orig with (%s)" % self.cfgValues[k]
      self.pgMiscellaneous.setOriginalHeater(self.cfgValues[k])
    else:
      self.pgMiscellaneous.setOriginalHeater(None)

  def loadConfigFile(self, fn):
    try:
      self.cfgBuffer = list(open(fn))
    except:
      return False

    self.configFile = fn

    self.processors = []
    gatheringHelpText = False
    helpTextString = ""
    helpKey = None

    self.cfgValues = {}
    self.helpText = {}

    prevLines = ""
    for ln in self.cfgBuffer:
      if gatheringHelpText:
        if reHelpTextEnd.match(ln):
          gatheringHelpText = False
          hk = helpKey.split()
          for k in hk:
            self.helpText[k] = helpTextString
          helpTextString = ""
          helpKey = None
          continue
        else:
          helpTextString += ln
          continue

      m = reHelpTextStart.match(ln)
      if m:
        t = m.groups()
        gatheringHelpText = True
        helpKey = t[0]
        continue

      if ln.rstrip().endswith("\\"):
        prevLines += ln.rstrip()[:-1]
        continue

      if prevLines != "":
        ln = prevLines + ln
        prevLines = ""

      if ln.lstrip().startswith("//"):
        continue

      if ln.lstrip().startswith("#define"):
        m = reDefQS.search(ln)
        if m:
          t = m.groups()
          if len(t) == 2:
            m = reDefQSm.search(ln)
            if m:
              t = m.groups()
              tt = re.findall(reDefQSm2, t[1])
              if len(tt) == 1:
                self.cfgValues[t[0]] = tt[0]
                continue
              elif len(tt) > 1:
                self.cfgValues[t[0]] = tt
                continue

        m = reDefine.search(ln)
        if m:
          t = m.groups()
          if len(t) == 2:
            if t[0] == 'DC_EXTRUDER': print "raw value (%s)" % t[1]
            self.cfgValues[t[0]] = t[1]
            continue

        m = reDefBool.search(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.cfgValues[t[0]] = True

    return True

  def onSaveConfig(self, evt):
    path = self.configFile
    if self.saveConfigFile(path):
      dlg = wx.MessageDialog(self, "File %s successfully written." % path,
                             "Save successful", wx.OK + wx.ICON_INFORMATION)

    else:
      dlg = wx.MessageDialog(self, "Unable to write to file %s." % path,
                             "File error", wx.OK + wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()

  def onSaveConfigAs(self, evt):
    wildcard = "Printer configuration (printer.*.h)|printer.*.h"

    dlg = wx.FileDialog(self, message = "Save as ...", defaultDir = self.dir,
                        defaultFile = "", wildcard = wildcard,
                        style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

    val = dlg.ShowModal()

    if val != wx.ID_OK:
      dlg.Destroy()
      return

    path = dlg.GetPath()
    dlg.Destroy()

    if self.saveConfigFile(path):
      dlg = wx.MessageDialog(self, "File %s successfully written." % path,
                             "Save successful", wx.OK + wx.ICON_INFORMATION)
      self.parent.setPrinterTabText("Printer <%s>" % os.path.basename(path))

    else:
      dlg = wx.MessageDialog(self, "Unable to write to file %s." % path,
                             "File error", wx.OK + wx.ICON_ERROR)
    dlg.ShowModal()
    dlg.Destroy()

  def saveConfigFile(self, path):
    ext = os.path.splitext(os.path.basename(path))[1]
    self.dir = os.path.dirname(path)

    if ext == "":
      path += ".h"

    try:
      fp = file(path, 'w')
    except:
      return False

    self.configFile = path

    values = {}

    for pg in self.pages:
      v1 = pg.getValues()
      for k in v1.keys():
        values[k] = v1[k]

    for ln in self.cfgBuffer:
      m = reDefineBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 2:
          if t[0] in values.keys() and values[t[0]] != "":
            fp.write(defineValueFormat % (t[0], values[t[0]]))
          else:
            fp.write("//" + ln)
          continue

      m = reDefBoolBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 1:
          if t[0] in values.keys() and values[t[0]]:
            fp.write(defineBoolFormat % t[0])
          else:
            fp.write("//" + ln)
          continue

      m = reCommDefBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 2:
          if t[0] in values.keys() and values[t[0]] != "":
            fp.write(defineValueFormat % (t[0], values[t[0]]))
          else:
            fp.write(ln)
          continue

      m = reCommDefBoolBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 1:
          if t[0] in values.keys() and values[t[0]]:
            fp.write(defineBoolFormat % t[0])
          else:
            fp.write(ln)
          continue

      fp.write(ln)

    fp.close()

    return True
