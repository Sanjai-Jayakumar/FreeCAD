import FreeCAD
import FreeCADGui as Gui
import os as _os


class TechDrawWorkbench(Gui.Workbench):
    "Technical Drawing workbench object"

    def __init__(self):
        self.__class__.Icon = (
            FreeCAD.getResourceDir()
            + "Mod/TechDraw/Resources/icons/preferences-techdraw.svg"
        )
        self.__class__.MenuText = "TechDraw"
        self.__class__.ToolTip = "Technical Drawing workbench"
        self._dim_watcher = None
        self._watcher_cls = None   # set in Initialize()

    def Initialize(self):
        import TechDrawGui
        from PySide.QtCore import QT_TRANSLATE_NOOP
        import FreeCAD as _FC
        import FreeCADGui as _Gui
        import os as _o
        import re as _re
        import traceback as _tb

        try:
            from PySide2 import QtCore as _QC, QtGui as _QG, QtWidgets as _QW
        except ImportError:
            from PySide import QtCore as _QC, QtGui as _QG
            _QW = _QG

        try:
            import TechDrawTools
        except ImportError as err:
            _FC.Console.PrintError(
                "Features from TechDrawTools package cannot be loaded. {err}\n".format(
                    err=str(err)))

        # ---- macro runner ----
        def run_macro(macro_name):
            home = _FC.getHomePath().rstrip('/\\')
            candidates = [
                _o.path.join(home, "Macro", macro_name),
                _o.path.join(_FC.getUserMacroDir(True), macro_name),
            ]
            for p in candidates:
                if _o.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8", errors="replace") as fh:
                            exec(compile(fh.read(), p, "exec"),
                                 {"__file__": p, "__name__": "__main__"})
                    except Exception as e:
                        _FC.Console.PrintError("BNC TechDraw: " + macro_name + " error: " + str(e) + "\n")
                        _FC.Console.PrintError(_tb.format_exc())
                    return
            _FC.Console.PrintError("BNC TechDraw: " + macro_name + " not found.\n")

        # ---- icon helper ----
        def icon(name):
            return _o.path.join(
                _FC.getHomePath().rstrip('/\\'),
                "Mod", "BNCTechDraw", "icons", name)

        # ---- command classes ----
        class CmdGenerateDrawing(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_GenerateDrawing.svg"),
                        "MenuText": "Generate Drawing",
                        "ToolTip": "Automatically generate 2D drawing from 3D model"}
            def IsActive(self): return _FC.ActiveDocument is not None
            def Activated(self): run_macro("GenerateDrawing.FCMacro")

        class CmdFillTitleBlock(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_InsertTitleBlock.svg"),
                        "MenuText": "Fill Title Block",
                        "ToolTip": "Auto-fill title block from model parameters"}
            def IsActive(self):
                if _FC.ActiveDocument is None: return False
                return any(o.TypeId == "TechDraw::DrawPage" for o in _FC.ActiveDocument.Objects)
            def Activated(self): run_macro("FillTitleBlock.FCMacro")

        class CmdInsertToleranceTable(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_InsertToleranceTable.svg"),
                        "MenuText": "Insert Tolerance Table",
                        "ToolTip": "Insert tolerance table into drawing sheet"}
            def IsActive(self):
                if _FC.ActiveDocument is None: return False
                return any(o.TypeId == "TechDraw::DrawPage" for o in _FC.ActiveDocument.Objects)
            def Activated(self): run_macro("InsertToleranceTable.FCMacro")

        class CmdAssemblyTable(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_AssemblyTable.svg"),
                        "MenuText": "Assembly Table",
                        "ToolTip": "Insert assembly parts list (BOM) into TechDraw sheet"}
            def IsActive(self):
                if _FC.ActiveDocument is None: return False
                return any(o.TypeId == "TechDraw::DrawPage" for o in _FC.ActiveDocument.Objects)
            def Activated(self): run_macro("AssemblyTable.FCMacro")

        class CmdBalloonAssembly(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_BalloonAssembly.svg"),
                        "MenuText": "Balloon Assembly",
                        "ToolTip": "Auto-create balloons on selected view numbered to match Assembly Table"}
            def IsActive(self):
                if _FC.ActiveDocument is None: return False
                return any(o.TypeId == "TechDraw::DrawPage" for o in _FC.ActiveDocument.Objects)
            def Activated(self): run_macro("BalloonAssembly.FCMacro")

        class CmdViewManager(object):
            def GetResources(self):
                return {"Pixmap": icon("BNC_ViewManager.svg"),
                        "MenuText": "View Manager",
                        "ToolTip": "Open View Manager to apply or insert named views"}
            def IsActive(self): return _FC.ActiveDocument is not None
            def Activated(self): run_macro("ViewManager.FCMacro")

        _Gui.addCommand("TechDraw_GenerateDrawing",     CmdGenerateDrawing())
        _Gui.addCommand("TechDraw_FillTitleBlock",       CmdFillTitleBlock())
        _Gui.addCommand("TechDraw_InsertToleranceTable", CmdInsertToleranceTable())
        _Gui.addCommand("TechDraw_AssemblyTable",        CmdAssemblyTable())
        _Gui.addCommand("TechDraw_BalloonAssembly",      CmdBalloonAssembly())
        _Gui.addCommand("TechDraw_ViewManager",          CmdViewManager())

        self._run_macro = run_macro

        # ---- Dimension panel watcher (defined here so closures work) ----

        def _parse_fmt(spec):
            m = _re.match(r'^(.*?)(%[-+]?\d*\.?\d*[a-zA-Z])(.*?)$', spec or '%.2w')
            if m:
                return m.group(1), m.group(2), m.group(3)
            return '', '%.2w', ''

        def _dim_value_str(dim, core):
            val = None
            # getRawValue() is the correct FreeCAD 1.1 TechDraw method
            try:
                val = float(dim.getRawValue())
            except Exception:
                pass
            # Fallback: parse getText() which returns the formatted string
            if val is None:
                try:
                    import re as _re2
                    txt = dim.getText()
                    m = _re2.search(r'[\d]+\.?[\d]*', txt)
                    if m:
                        val = float(m.group())
                except Exception:
                    pass
            if val is None:
                return '?'
            try:
                py = _re.sub(r'%([^a-zA-Z]*)w', r'%\1f', core or '%.2w')
                py = _re.sub(r'%([^a-zA-Z]*)v', r'%\1f', py)
                return py % abs(val)
            except Exception:
                return "%.2f" % abs(val)

        _TOL_DEFAULT_RE = _re.compile(r'^%[+\-]?\d*\.?\d*[wv]$')

        def _clean_tol(val):
            if not val:
                return ''
            if _TOL_DEFAULT_RE.match(val.strip()):
                return ''
            return val

        class _DimSelObs(object):
            """Selection observer — captures the TechDraw dimension the instant
            the user clicks it, before the task panel clears the selection."""
            def __init__(self):
                self.last_dim = None
            def addSelection(self, doc, obj, sub, pnt):
                try:
                    d = _FC.getDocument(doc).getObject(obj)
                    if d and d.TypeId == "TechDraw::DrawViewDimension":
                        self.last_dim = d
                except Exception:
                    pass
            def removeSelection(self, doc, obj, sub): pass
            def setSelection(self, doc): pass
            def clearSelection(self, doc): pass

        class DimPanelWatcher(_QC.QObject):
            def __init__(self):
                super(DimPanelWatcher, self).__init__()
                self._last_panel = None
                self._active_dim = None
                self._sel_obs = _DimSelObs()
                _Gui.Selection.addObserver(self._sel_obs)
                self._timer = _QC.QTimer(self)
                self._timer.timeout.connect(self._poll)
                self._timer.start(350)

            def stop(self):
                self._timer.stop()
                try:
                    _Gui.Selection.removeObserver(self._sel_obs)
                except Exception:
                    pass

            def _find_panel(self):
                # Strategy: find any QLabel whose text contains 'decimal'
                # (unique to the TechDraw dimension task panel:
                # "Number of decimals").  Walk UP the parent chain to find
                # the first ancestor that (a) has a layout and (b) also
                # contains a 'format' label — that ancestor is our target.
                mw = _Gui.getMainWindow()
                for lbl in mw.findChildren(_QW.QLabel):
                    if 'decimal' in lbl.text().lower():
                        p = lbl.parent()
                        while p is not None and p is not mw:
                            lo = p.layout()
                            if lo is not None:
                                texts = [l.text().lower()
                                         for l in p.findChildren(_QW.QLabel)]
                                if (any('decimal' in t for t in texts) and
                                        any('format' in t for t in texts)):
                                    return p
                            p = p.parent()
                return None

            def _cleanup_orphans(self):
                try:
                    mw = _Gui.getMainWindow()
                    for w in mw.findChildren(_QW.QGroupBox):
                        if w.objectName() == "BNC_AssocTexts":
                            w.hide()
                            w.setParent(None)
                            w.deleteLater()
                except Exception:
                    pass

            def _poll(self):
                try:
                    panel = self._find_panel()
                    if panel is None:
                        if self._last_panel is not None:
                            self._cleanup_orphans()
                        self._last_panel = None
                        self._active_dim = None
                        return
                    if panel is self._last_panel:
                        return
                    self._active_dim = self._grab_dim()
                    self._inject(panel)
                    self._last_panel = panel
                except Exception as _pe:
                    _FC.Console.PrintError(
                        "BNC DimPanel poll: " + str(_pe) + "\n")

            def _grab_dim(self):
                # 1. Selection observer — captured before task panel cleared selection
                try:
                    d = self._sel_obs.last_dim
                    if d is not None and 'Dimension' in d.TypeId:
                        return d
                except Exception:
                    pass
                # 2. getInEdit
                try:
                    vp = _Gui.ActiveDocument.getInEdit()
                    if vp is not None:
                        obj = vp.Object
                        if 'Dimension' in obj.TypeId:
                            return obj
                except Exception:
                    pass
                # 3. Current selection
                for obj in _Gui.Selection.getSelection():
                    try:
                        if 'Dimension' in obj.TypeId:
                            return obj
                    except Exception:
                        pass
                # 4. findObjects (most reliable type search)
                doc = _FC.ActiveDocument
                if doc:
                    try:
                        dims = doc.findObjects(Type="TechDraw::DrawViewDimension")
                        if dims:
                            return dims[0]
                    except Exception:
                        pass
                    # 5. Broad fallback — any object with FormatSpec + Value
                    for obj in doc.Objects:
                        try:
                            if (hasattr(obj, 'FormatSpec') and
                                    hasattr(obj, 'Value') and
                                    hasattr(obj, 'References2D')):
                                return obj
                        except Exception:
                            pass
                return None

            def _inject(self, panel_w):
                try:
                    layout = panel_w.layout()
                    if layout is None:
                        _FC.Console.PrintError(
                            "BNC DimPanel: panel layout is None\n")
                        return
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        w = item.widget() if item else None
                        if w and w.objectName() == "BNC_AssocTexts":
                            return
                    group = self._build_group()
                    layout.addWidget(group)
                    panel_w.adjustSize()
                except Exception as _ie:
                    _FC.Console.PrintError(
                        "BNC DimPanel inject: " + str(_ie) + "\n")

            def _build_group(self):
                dim = self._active_dim

                group = _QW.QGroupBox("Associated Texts")
                group.setObjectName("BNC_AssocTexts")
                group.setSizePolicy(_QW.QSizePolicy.Expanding, _QW.QSizePolicy.Maximum)
                group.setStyleSheet(
                    "QGroupBox { background-color: transparent; font-weight: bold;"
                    " font-size: 12px; border: 1px solid palette(mid);"
                    " border-radius: 3px; margin-top: 6px; padding-top: 4px; }"
                    "QGroupBox::title { subcontrol-origin: margin; left: 8px; }")

                root = _QW.QVBoxLayout(group)
                root.setSpacing(6)
                root.setContentsMargins(8, 14, 8, 8)

                # ── Prefix | Value | Suffix ──────────────────────────
                pvs = _QW.QHBoxLayout()
                pvs.setSpacing(4)

                def _col(label_text, widget):
                    col = _QW.QVBoxLayout()
                    col.setSpacing(2)
                    lbl = _QW.QLabel(label_text)
                    lbl.setAlignment(_QC.Qt.AlignCenter)
                    lbl.setStyleSheet("font-size: 12px; color: #444; font-weight: normal;")
                    col.addWidget(lbl)
                    col.addWidget(widget)
                    return col

                prefix_edit = _QW.QLineEdit()
                prefix_edit.setObjectName("BNC_prefix")
                prefix_edit.setAlignment(_QC.Qt.AlignCenter)
                prefix_edit.setPlaceholderText("e.g. R")
                prefix_edit.setFixedWidth(72)
                prefix_edit.setFixedHeight(28)

                value_lbl = _QW.QLabel("—")
                value_lbl.setObjectName("BNC_value")
                value_lbl.setAlignment(_QC.Qt.AlignCenter)
                value_lbl.setFixedWidth(90)
                value_lbl.setFixedHeight(28)
                value_lbl.setStyleSheet(
                    "background:#f0f4f8; border:1px solid #bbb; border-radius:3px;"
                    "font-weight:bold; font-size:13px;")

                suffix_edit = _QW.QLineEdit()
                suffix_edit.setObjectName("BNC_suffix")
                suffix_edit.setAlignment(_QC.Qt.AlignCenter)
                suffix_edit.setPlaceholderText("e.g. mm")
                suffix_edit.setFixedWidth(72)
                suffix_edit.setFixedHeight(28)

                pvs.addLayout(_col("Prefix", prefix_edit))
                pvs.addStretch()
                pvs.addLayout(_col("Main Value", value_lbl))
                pvs.addStretch()
                pvs.addLayout(_col("Suffix", suffix_edit))
                root.addLayout(pvs)

                # ── Top / Bottom ──────────────────────────────────────
                grid = _QW.QGridLayout()
                grid.setSpacing(4)
                grid.setColumnStretch(1, 1)

                def _row_lbl(t):
                    l = _QW.QLabel(t)
                    l.setStyleSheet("font-size: 12px; font-weight: normal;")
                    return l

                top_edit = _QW.QLineEdit()
                top_edit.setObjectName("BNC_top")
                top_edit.setPlaceholderText("text above value")
                top_edit.setFixedHeight(26)

                bot_edit = _QW.QLineEdit()
                bot_edit.setObjectName("BNC_bottom")
                bot_edit.setPlaceholderText("text below value")
                bot_edit.setFixedHeight(26)

                grid.addWidget(_row_lbl("Top:"),    0, 0)
                grid.addWidget(top_edit,            0, 1)
                grid.addWidget(_row_lbl("Bottom:"), 1, 0)
                grid.addWidget(bot_edit,            1, 1)
                root.addLayout(grid)

                def _ann_names(d):
                    safe = d.Label.replace(" ", "_").replace(".", "_")
                    return "BNC_TA_" + safe, "BNC_BA_" + safe

                def _find_page(d):
                    doc = _FC.ActiveDocument
                    if not doc:
                        return None
                    try:
                        pv = d.getParent()
                        for obj in doc.Objects:
                            if obj.TypeId == "TechDraw::DrawPage":
                                if pv in getattr(obj, 'Views', []):
                                    return obj
                    except Exception:
                        pass
                    for obj in doc.Objects:
                        if obj.TypeId == "TechDraw::DrawPage":
                            return obj
                    return None

                def _set_annotation(page, name, text, x, y, fs):
                    doc = _FC.ActiveDocument
                    if not doc:
                        return
                    ann = doc.getObject(name)
                    if text:
                        if ann is None:
                            ann = doc.addObject(
                                "TechDraw::DrawViewAnnotation", name)
                            page.addView(ann)
                        ann.Text = [text]
                        ann.X = x
                        ann.Y = y
                        try:
                            ann.TextSize = fs
                        except Exception:
                            pass
                    else:
                        if ann is not None:
                            try:
                                page.removeView(ann)
                            except Exception:
                                pass
                            try:
                                doc.removeObject(name)
                            except Exception:
                                pass

                # ── Populate from dim ─────────────────────────────────
                if dim is not None:
                    prefix, core, suffix = _parse_fmt(dim.FormatSpec)
                    prefix_edit.setText(prefix.strip())
                    suffix_edit.setText(suffix.strip())
                    value_lbl.setText(_dim_value_str(dim, core))
                    # Read top/bottom from annotation objects
                    doc0 = _FC.ActiveDocument
                    tn, bn = _ann_names(dim)
                    ta = doc0.getObject(tn) if doc0 else None
                    ba = doc0.getObject(bn) if doc0 else None
                    top_edit.setText((ta.Text[0] if ta and ta.Text else '') if ta else '')
                    bot_edit.setText((ba.Text[0] if ba and ba.Text else '') if ba else '')

                # ── Live update (debounced 500 ms) ────────────────────
                timer = _QC.QTimer(group)
                timer.setSingleShot(True)
                _dim_ref = [dim]

                def _apply():
                    d = _dim_ref[0]
                    if d is None:
                        return
                    try:
                        saved_x = getattr(d, 'X', None)
                        saved_y = getattr(d, 'Y', None)

                        p = prefix_edit.text().strip()
                        s = suffix_edit.text().strip()
                        _, c, _ = _parse_fmt(d.FormatSpec)
                        new_fmt = (p + " " if p else "") + c + (" " + s if s else "")
                        d.FormatSpec = new_fmt

                        # Restore tolerance props to defaults (we use annotations)
                        if hasattr(d, 'ArbitraryTolerances'):
                            d.ArbitraryTolerances = False
                        if hasattr(d, 'EqualTolerance'):
                            d.EqualTolerance = True
                        if hasattr(d, 'FormatSpecOverTolerance'):
                            d.FormatSpecOverTolerance = '%+.2w'
                        if hasattr(d, 'FormatSpecUnderTolerance'):
                            d.FormatSpecUnderTolerance = '%+.2w'

                        if _FC.ActiveDocument:
                            _FC.ActiveDocument.recompute([d])

                        try:
                            if saved_x is not None:
                                d.X = saved_x
                            if saved_y is not None:
                                d.Y = saved_y
                        except Exception:
                            pass

                        # Place top/bottom as DrawViewAnnotation above/below
                        top_text = top_edit.text().strip()
                        bot_text = bot_edit.text().strip()
                        page = _find_page(d)
                        if page is not None:
                            try:
                                fs = float(getattr(d, 'Fontsize',
                                           getattr(d, 'FontSize', 5.0)))
                            except Exception:
                                fs = 5.0
                            offset = fs * 1.6

                            # Coordinate systems in TechDraw:
                            # - DrawProjGroup.X/Y and DrawViewPart.X/Y:
                            #     page-CENTER-origin, Y-up, mm
                            # - DrawProjGroupItem.X/Y:
                            #     RELATIVE to its parent DrawProjGroup,
                            #     same direction/units
                            # - DrawViewDimension.X/Y:
                            #     RELATIVE to the view's center on page,
                            #     same direction/units
                            # - DrawViewAnnotation.X/Y:
                            #     page-BOTTOM-LEFT-origin, Y-up, mm
                            #
                            # So: label center-origin = (projGroup.XY +
                            #     item.XY + dim.XY).  Then convert:
                            #     ann.X = label_center_X + pw/2
                            #     ann.Y = label_center_Y + ph/2
                            # DrawProjGroup.X/Y and DrawViewPart.X/Y use
                            # page BOTTOM-LEFT origin (Y-up, mm) — same as
                            # DrawViewAnnotation.X/Y.
                            # DrawProjGroupItem.X/Y is relative to its group.
                            # DrawViewDimension.X/Y is relative to view center.
                            # → ann.X = view_BL_X + dim.X  (no conversion)
                            # → ann.Y = view_BL_Y + dim.Y  (no conversion)
                            vx = vy = 0.0
                            try:
                                refs = d.References2D
                                if refs:
                                    pv = refs[0][0]
                                    vx = float(getattr(pv, 'X', 0))
                                    vy = float(getattr(pv, 'Y', 0))
                                    # DrawProjGroupItem.X/Y is relative to group
                                    if getattr(pv, 'TypeId', '') == \
                                            "TechDraw::DrawProjGroupItem":
                                        doc2 = _FC.ActiveDocument
                                        if doc2:
                                            for _pg in doc2.Objects:
                                                if _pg.TypeId == \
                                                      "TechDraw::DrawProjGroup":
                                                    if pv in getattr(
                                                            _pg, 'Views', []):
                                                        vx += float(
                                                            getattr(_pg,'X',0))
                                                        vy += float(
                                                            getattr(_pg,'Y',0))
                                                        break
                            except Exception:
                                pass

                            dx = float(getattr(d, 'X', 0))
                            dy = float(getattr(d, 'Y', 0))
                            ann_x = vx + dx
                            ann_y = vy + dy

                            tn, bn = _ann_names(d)
                            _set_annotation(page, tn, top_text,
                                            ann_x, ann_y + offset, fs)
                            _set_annotation(page, bn, bot_text,
                                            ann_x, ann_y - offset, fs)
                        if _FC.ActiveDocument:
                            _FC.ActiveDocument.recompute()

                    except Exception as e:
                        _FC.Console.PrintError("BNC AssocTexts: " + str(e) + "\n")

                for w in [prefix_edit, suffix_edit, top_edit, bot_edit]:
                    w.textChanged.connect(lambda _: timer.start(500))
                timer.timeout.connect(_apply)

                return group

        # Save class so Activated() can instantiate it
        self._watcher_cls = DimPanelWatcher

    # ------------------------------------------------------------------

    def _bnc_toolbar(self, show):
        try:
            try:
                from PySide2 import QtCore, QtGui, QtWidgets
            except ImportError:
                from PySide import QtCore, QtGui
                QtWidgets = QtGui

            mw = Gui.getMainWindow()
            if mw is None:
                return
            tb = mw.findChild(QtWidgets.QToolBar, "BNC_TechDraw_Tools")
            if not show:
                if tb is not None:
                    tb.hide()
                return
            if tb is not None:
                tb.show()
                return

            import os as _o2
            icon_dir = _o2.path.join(FreeCAD.getHomePath().rstrip('/\\'),
                                     "Mod", "BNCTechDraw", "icons")
            tb = QtWidgets.QToolBar("BNC TechDraw Tools", mw)
            tb.setObjectName("BNC_TechDraw_Tools")
            tb.setWindowTitle("BNC TechDraw Tools")
            tb.setMovable(True)
            tb.setIconSize(QtCore.QSize(24, 24))
            tb.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            run = getattr(self, "_run_macro", None)
            for icon_file, tip, macro in [
                ("BNC_GenerateDrawing.svg",     "Generate Drawing",       "GenerateDrawing.FCMacro"),
                ("BNC_InsertTitleBlock.svg",     "Fill Title Block",       "FillTitleBlock.FCMacro"),
                ("BNC_InsertToleranceTable.svg", "Insert Tolerance Table", "InsertToleranceTable.FCMacro"),
                ("BNC_AssemblyTable.svg",        "Assembly Table",         "AssemblyTable.FCMacro"),
                ("BNC_BalloonAssembly.svg",      "Balloon Assembly",       "BalloonAssembly.FCMacro"),
                ("BNC_ExportPDF.svg",            "Export PDF",             "ExportPDF.FCMacro"),
            ]:
                icon_path = _o2.path.join(icon_dir, icon_file)
                action = (QtWidgets.QAction(QtGui.QIcon(icon_path), tip, mw)
                          if _o2.path.exists(icon_path)
                          else QtWidgets.QAction(tip, mw))
                action.setToolTip(tip)
                if run is not None:
                    action.triggered.connect(lambda checked=False, m=macro: run(m))
                tb.addAction(action)
            mw.addToolBar(QtCore.Qt.TopToolBarArea, tb)
        except Exception as e:
            import traceback
            FreeCAD.Console.PrintError("BNC TechDraw toolbar error: " + str(e) + "\n")
            FreeCAD.Console.PrintError(traceback.format_exc())

    def Activated(self):
        self._bnc_toolbar(True)
        if self._dim_watcher is None and self._watcher_cls is not None:
            self._dim_watcher = self._watcher_cls()

    def Deactivated(self):
        self._bnc_toolbar(False)
        if self._dim_watcher is not None:
            self._dim_watcher.stop()
            self._dim_watcher = None

    def GetClassName(self):
        return "TechDrawGui::Workbench"


Gui.addWorkbench(TechDrawWorkbench())

FreeCAD.addExportType("Technical Drawing (*.svg *.dxf *.pdf)", "TechDrawGui")

FreeCAD.__unit_test__ += ["TestTechDrawGui"]
