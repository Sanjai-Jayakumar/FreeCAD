/***************************************************************************
 *   Copyright (c) 2021 Uwe Stöhr <uwestoehr@lyx.org>                      *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

# include <cmath>
# include <limits>
# include <QMessageBox>
# include <regex>

#include <App/Document.h>
#include <Base/Tools.h>
#include <Gui/BitmapFactory.h>
#include <Gui/Command.h>
#include <Gui/Document.h>
#include <Gui/MainWindow.h>
#include <Gui/Selection/Selection.h>
#include <Gui/Selection/SelectionObject.h>
#include <Mod/TechDraw/App/DrawUtil.h>
#include <Mod/TechDraw/App/DrawViewPart.h>

#include "ui_TaskDimension.h"
#include "TaskDimension.h"
#include "QGIViewDimension.h"
#include "ViewProviderDimension.h"


using namespace Gui;
using namespace TechDraw;
using namespace TechDrawGui;

TaskDimension::TaskDimension(QGIViewDimension *parent, ViewProviderDimension *dimensionVP) :
    ui(new Ui_TaskDimension),
    m_parent(parent),
    m_dimensionVP(dimensionVP)
{
    ui->setupUi(this);

    // Number of Decimals
    std::string currentFormat = parent->getDimFeat()->FormatSpec.getStrValue();
    std::smatch match;
    std::regex specRegex("%\\.([0-9]+)([fFrRgGwWeE])");

    if (std::regex_search(currentFormat, match, specRegex) && match.size() > 2) {
        int numDecimals = std::stoi(match[1].str());
        m_originalFormatChar = match[2].str();
        m_formatPrefix = match.prefix().str();
        m_formatSuffix = match.suffix().str();
        ui->sbNumDecimals->setValue(numDecimals);
    } else {
        // Handle the case where no format specifier is found
        ui->sbNumDecimals->setValue(2);
        m_originalFormatChar = "w";
        // If no specifier, the whole string is the prefix
        m_formatPrefix = currentFormat;
        m_formatSuffix = "";
    }
    connect(ui->sbNumDecimals, qOverload<int>(&QSpinBox::valueChanged), this, &TaskDimension::onNumDecChanged);

    // Tolerancing
    ui->cbTheoreticallyExact->setChecked(parent->getDimFeat()->TheoreticalExact.getValue());
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
    connect(ui->cbTheoreticallyExact, &QCheckBox::checkStateChanged, this, &TaskDimension::onTheoreticallyExactChanged);
#else
    connect(ui->cbTheoreticallyExact, &QCheckBox::stateChanged, this, &TaskDimension::onTheoreticallyExactChanged);
#endif
    // if TheoreticalExact disable tolerances
    if (parent->getDimFeat()->TheoreticalExact.getValue()) {
        ui->cbEqualTolerance->setDisabled(true);
        ui->qsbOvertolerance->setDisabled(true);
        ui->qsbUndertolerance->setDisabled(true);
        ui->leFormatSpecifierOverTolerance->setDisabled(true);
        ui->leFormatSpecifierUnderTolerance->setDisabled(true);
    }
    ui->cbEqualTolerance->setChecked(parent->getDimFeat()->EqualTolerance.getValue());
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
    connect(ui->cbEqualTolerance, &QCheckBox::checkStateChanged, this, &TaskDimension::onEqualToleranceChanged);
#else
    connect(ui->cbEqualTolerance, &QCheckBox::stateChanged, this, &TaskDimension::onEqualToleranceChanged);
#endif
    // if EqualTolerance overtolernace must not be negative
    if (parent->getDimFeat()->EqualTolerance.getValue())
        ui->qsbOvertolerance->setMinimum(0.0);
    if ((parent->getDimFeat()->Type.isValue("Angle")) ||
        (parent->getDimFeat()->Type.isValue("Angle3Pt"))) {
        ui->qsbOvertolerance->setUnit(Base::Unit::Angle);
        ui->qsbUndertolerance->setUnit(Base::Unit::Angle);
    }
    else {
        ui->qsbOvertolerance->setUnit(Base::Unit::Length);
        ui->qsbUndertolerance->setUnit(Base::Unit::Length);
    }
    ui->qsbOvertolerance->setValue(parent->getDimFeat()->OverTolerance.getValue());
    ui->qsbUndertolerance->setValue(parent->getDimFeat()->UnderTolerance.getValue());
    connect(ui->qsbOvertolerance, qOverload<double>(&QuantitySpinBox::valueChanged), this, &TaskDimension::onOvertoleranceChanged);
    connect(ui->qsbUndertolerance, qOverload<double>(&QuantitySpinBox::valueChanged), this, &TaskDimension::onUndertoleranceChanged);
    // undertolerance is disabled when EqualTolerance is true
    if (ui->cbEqualTolerance->isChecked()) {
        ui->qsbUndertolerance->setDisabled(true);
        ui->leFormatSpecifierUnderTolerance->setDisabled(true);
    }

    // Formatting
    std::string StringValue = parent->getDimFeat()->FormatSpec.getValue();
    QString qs = QString::fromUtf8(StringValue.data(), StringValue.size());
    ui->leFormatSpecifier->setText(qs);
    connect(ui->leFormatSpecifier, &QLineEdit::textChanged, this, &TaskDimension::onFormatSpecifierChanged);
    ui->cbArbitrary->setChecked(parent->getDimFeat()->Arbitrary.getValue());
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
    connect(ui->cbArbitrary, &QCheckBox::checkStateChanged, this, &TaskDimension::onArbitraryChanged);
#else
    connect(ui->cbArbitrary, &QCheckBox::stateChanged, this, &TaskDimension::onArbitraryChanged);
#endif
    // ANVIL CAD: dedicated display-only value box. It is shown only while
    // "Edit value" is ticked, and it is the ONLY control that writes the
    // override - the Format specifier / Prefix / Suffix fields are left alone.
    {
        bool arb = parent->getDimFeat()->Arbitrary.getValue();
        ui->leEditValue->setVisible(arb);
        ui->labelEditValue->setVisible(arb);
        if (arb) {
            ui->leEditValue->setText(
                QString::fromStdString(parent->getDimFeat()->FormatSpec.getStrValue()));
        }
        connect(ui->leEditValue, &QLineEdit::textEdited, this,
                &TaskDimension::onEditValueChanged);
    }
    StringValue = parent->getDimFeat()->FormatSpecOverTolerance.getValue();
    qs = QString::fromUtf8(StringValue.data(), StringValue.size());
    ui->leFormatSpecifierOverTolerance->setText(qs);
    StringValue = parent->getDimFeat()->FormatSpecUnderTolerance.getValue();
    qs = QString::fromUtf8(StringValue.data(), StringValue.size());
    ui->leFormatSpecifierUnderTolerance->setText(qs);
    connect(ui->leFormatSpecifierOverTolerance, &QLineEdit::textChanged, this, &TaskDimension::onFormatSpecifierOverToleranceChanged);
    connect(ui->leFormatSpecifierUnderTolerance, &QLineEdit::textChanged, this, &TaskDimension::onFormatSpecifierUnderToleranceChanged);
    ui->cbArbitraryTolerances->setChecked(parent->getDimFeat()->ArbitraryTolerances.getValue());
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
    connect(ui->cbArbitraryTolerances, &QCheckBox::checkStateChanged, this, &TaskDimension::onArbitraryTolerancesChanged);
#else
    connect(ui->cbArbitraryTolerances, &QCheckBox::stateChanged, this, &TaskDimension::onArbitraryTolerancesChanged);
#endif

    // ANVIL CAD: Creo-style Tolerance mode dropdown. Presents the underlying
    // TheoreticalExact / EqualTolerance / Over / Under tolerance controls as a
    // single Nominal / Symmetric / Plus-Minus / Basic selector and reveals the
    // dedicated +/- value boxes only for the modes that use them.
    {
        ui->comboTolType->addItem(tr("Nominal"));                  // 0 no tolerance
        ui->comboTolType->addItem(QString::fromUtf8("Symmetric (\xC2\xB1)")); // 1 equal +/-
        ui->comboTolType->addItem(tr("Plus-Minus"));               // 2 separate + / -
        ui->comboTolType->addItem(tr("Basic"));                    // 3 theoretically exact
        auto* df = parent->getDimFeat();
        int initMode;
        if (df->TheoreticalExact.getValue())
            initMode = 3;
        else if (df->EqualTolerance.getValue())
            initMode = 1;
        else if (df->OverTolerance.getValue() == 0.0 && df->UnderTolerance.getValue() == 0.0)
            initMode = 0;
        else
            initMode = 2;
        ui->comboTolType->setCurrentIndex(initMode);
        updateToleranceModeUi(initMode);
        connect(ui->comboTolType, qOverload<int>(&QComboBox::currentIndexChanged),
                this, &TaskDimension::onTolTypeChanged);
    }

    // Reference
    std::regex refRegex("\\(%\\.([0-9]+)([fFrRgGwWeE])\\)");
    const bool hasReference = std::regex_search(currentFormat, refRegex);
    ui->cbReference->setChecked(hasReference);
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
    connect(ui->cbReference, &QCheckBox::checkStateChanged, this, &TaskDimension::onReferenceChanged);
#else
    connect(ui->cbReference, &QCheckBox::stateChanged, this, &TaskDimension::onReferenceChanged);
#endif

    // Display Style
    if (dimensionVP) {
        ui->cbArrowheads->setChecked(dimensionVP->FlipArrowheads.getValue());
#if QT_VERSION >= QT_VERSION_CHECK(6,7,0)
        connect(ui->cbArrowheads, &QCheckBox::checkStateChanged, this, &TaskDimension::onFlipArrowheadsChanged);
#else
        connect(ui->cbArrowheads, &QCheckBox::stateChanged, this, &TaskDimension::onFlipArrowheadsChanged);
#endif
        ui->dimensionColor->setColor(dimensionVP->Color.getValue().asValue<QColor>());
        connect(ui->dimensionColor, &ColorButton::changed, this, &TaskDimension::onColorChanged);
        ui->qsbFontSize->setValue(dimensionVP->Fontsize.getValue());
        ui->qsbFontSize->setUnit(Base::Unit::Length);
        ui->qsbFontSize->setMinimum(0);
        connect(ui->qsbFontSize, qOverload<double>(&QuantitySpinBox::valueChanged), this, &TaskDimension::onFontsizeChanged);
        ui->comboDrawingStyle->setCurrentIndex(dimensionVP->StandardAndStyle.getValue());
        connect(ui->comboDrawingStyle, qOverload<int>(&QComboBox::currentIndexChanged), this, &TaskDimension::onDrawingStyleChanged);
    }

    // Lines
    ui->rbOverride->setChecked(parent->getDimFeat()->AngleOverride.getValue());
    connect(ui->rbOverride, &QRadioButton::toggled, this, &TaskDimension::onOverrideToggled);
    ui->dsbDimAngle->setValue(parent->getDimFeat()->LineAngle.getValue());
    connect(ui->dsbDimAngle, qOverload<double>(&QDoubleSpinBox::valueChanged), this, &TaskDimension::onDimAngleChanged);
    ui->dsbExtAngle->setValue(parent->getDimFeat()->ExtensionAngle.getValue());
    connect(ui->dsbExtAngle, qOverload<double>(&QDoubleSpinBox::valueChanged), this, &TaskDimension::onExtAngleChanged);
    connect(ui->pbDimUseDefault, &QPushButton::clicked, this, &TaskDimension::onDimUseDefaultClicked);
    connect(ui->pbDimUseSelection, &QPushButton::clicked, this, &TaskDimension::onDimUseSelectionClicked);
    connect(ui->pbExtUseDefault, &QPushButton::clicked, this, &TaskDimension::onExtUseDefaultClicked);
    connect(ui->pbExtUseSelection, &QPushButton::clicked, this, &TaskDimension::onExtUseSelectionClicked);

    Gui::Document* doc = m_dimensionVP->getDocument();
    doc->openCommand("TaskDimension");
}

TaskDimension::~TaskDimension()
{
}

bool TaskDimension::accept()
{
    if (m_dimensionVP.expired()) {
        QMessageBox::warning(Gui::getMainWindow(), QObject::tr("Missing Dimension"),
                                               QObject::tr("Dimension not found. Was it deleted? Cannot continue."));
        return true;
    }
    Gui::Document* doc = m_dimensionVP->getDocument();
    m_dimensionVP->getObject()->purgeTouched();
    doc->commitCommand();
    doc->resetEdit();

    return true;
}

bool TaskDimension::reject()
{
    if (m_dimensionVP.expired()) {
        QMessageBox::warning(Gui::getMainWindow(), QObject::tr("Missing Dimension"),
                                               QObject::tr("Dimension not found. Was it deleted? Cannot continue."));
        return true;
    }
    Gui::Document* doc = m_dimensionVP->getDocument();
    doc->abortCommand();
    recomputeFeature();
    m_parent->updateView(true);
    m_dimensionVP->getObject()->purgeTouched();
    doc->resetEdit();

    return true;
}

void TaskDimension::recomputeFeature()
{
    if (m_dimensionVP.expired()) {
        // guard against deletion while this dialog is running
        return;
    }
    App::DocumentObject* objVP = m_dimensionVP->getObject();
    assert(objVP);
    objVP->recomputeFeature();
}

void TaskDimension::onNumDecChanged(int decimals)
{
    std::string currentFormat = ui->leFormatSpecifier->text().toUtf8().constData();

    std::smatch match;
    std::regex specRegex("%\\.([0-9]+)([fFrRgGwWeE])");

    // Re-parse the current string
    if (std::regex_search(currentFormat, match, specRegex) && match.size() > 2) {
        m_originalFormatChar = match[2].str();
        m_formatPrefix = match.prefix().str();
        m_formatSuffix = match.suffix().str();
    } else {
        // if the user deleted the specifier, assume the whole string
        // is a prefix and insert the specifier.
        m_formatPrefix = currentFormat;
        m_formatSuffix = "";
        m_originalFormatChar = "w"; // Default fallback format char
    }

    // Rebuild the string
    std::string newFormatSpec = m_formatPrefix
                              + "%." + std::to_string(decimals) + m_originalFormatChar
                              + m_formatSuffix;

    // Update the UI
    ui->leFormatSpecifier->blockSignals(true);
    ui->leFormatSpecifier->setText(QString::fromStdString(newFormatSpec));
    ui->leFormatSpecifier->blockSignals(false);

    onFormatSpecifierChanged();
}

void TaskDimension::onReferenceChanged()
{
    std::string currentFormat = ui->leFormatSpecifier->text().toUtf8().constData();
    std::string newFormat = currentFormat;
    bool isChecked = ui->cbReference->isChecked();

    // Find a format specifier
    std::regex specRegex("%\\.([0-9]+)([fFrRgGwWeE])");
    // Find a reference format specifier
    std::regex refRegex("\\((%\\.([0-9]+)([fFrRgGwWeE]))\\)");

    if (isChecked) {
        newFormat = std::regex_replace(currentFormat, specRegex, "($&)");
    } else {
        newFormat = std::regex_replace(currentFormat, refRegex, "$1");
    }

    // Update UI
    ui->leFormatSpecifier->blockSignals(true);
    ui->leFormatSpecifier->setText(QString::fromStdString(newFormat));
    ui->leFormatSpecifier->blockSignals(false);

    onFormatSpecifierChanged();
}

void TaskDimension::onTheoreticallyExactChanged()
{
    m_parent->getDimFeat()->TheoreticalExact.setValue(ui->cbTheoreticallyExact->isChecked());
    // if TheoreticalExact disable tolerances and set them to zero
    if (ui->cbTheoreticallyExact->isChecked()) {
        ui->qsbOvertolerance->setValue(0.0);
        ui->qsbUndertolerance->setValue(0.0);
        ui->cbEqualTolerance->setDisabled(true);
        ui->qsbOvertolerance->setDisabled(true);
        ui->qsbUndertolerance->setDisabled(true);
        ui->leFormatSpecifierOverTolerance->setDisabled(true);
        ui->leFormatSpecifierUnderTolerance->setDisabled(true);
        ui->cbArbitraryTolerances->setDisabled(true);
        ui->cbArbitraryTolerances->setChecked(false);
    }
    else {
        ui->cbEqualTolerance->setDisabled(false);
        ui->qsbOvertolerance->setDisabled(false);
        ui->leFormatSpecifierOverTolerance->setDisabled(false);
        ui->cbArbitraryTolerances->setDisabled(false);
        if (!ui->cbEqualTolerance->isChecked()) {
            ui->qsbUndertolerance->setDisabled(false);
            ui->leFormatSpecifierUnderTolerance->setDisabled(false);
        }
    }
    recomputeFeature();
}

void TaskDimension::onEqualToleranceChanged()
{
    m_parent->getDimFeat()->EqualTolerance.setValue(ui->cbEqualTolerance->isChecked());
    // if EqualTolerance set negated overtolerance for untertolerance
    // then also the OverTolerance must be positive
    if (ui->cbEqualTolerance->isChecked()) {
        // if OverTolerance is negative or zero, first set it to zero
        if (ui->qsbOvertolerance->value().getValue() < 0)
            ui->qsbOvertolerance->setValue(0.0);
        ui->qsbOvertolerance->setMinimum(0.0);
        ui->qsbUndertolerance->setValue(-1.0 * ui->qsbOvertolerance->value().getValue());
        ui->qsbUndertolerance->setUnit(ui->qsbOvertolerance->value().getUnit());
        ui->qsbUndertolerance->setDisabled(true);
        ui->leFormatSpecifierUnderTolerance->setDisabled(true);
    }
    else {
        ui->qsbOvertolerance->setMinimum(-std::numeric_limits<double>::max());
        if (!ui->cbTheoreticallyExact->isChecked()) {
            ui->qsbUndertolerance->setDisabled(false);
            ui->leFormatSpecifierUnderTolerance->setDisabled(false);
        }
    }
    recomputeFeature();
}

void TaskDimension::onOvertoleranceChanged()
{
    m_parent->getDimFeat()->OverTolerance.setValue(ui->qsbOvertolerance->value().getValue());
    // if EqualTolerance set negated overtolerance for untertolerance
    if (ui->cbEqualTolerance->isChecked()) {
        ui->qsbUndertolerance->setValue(-1.0 * ui->qsbOvertolerance->value().getValue());
        ui->qsbUndertolerance->setUnit(ui->qsbOvertolerance->value().getUnit());
    }
    recomputeFeature();
}

void TaskDimension::onUndertoleranceChanged()
{
    m_parent->getDimFeat()->UnderTolerance.setValue(ui->qsbUndertolerance->value().getValue());
    recomputeFeature();
}

// ANVIL CAD: Creo-style tolerance mode selector. Maps the chosen mode onto the
// underlying TheoreticalExact / EqualTolerance / Over / Under properties by
// driving the (now hidden) checkboxes so all their existing side-effect logic
// runs, then reveals only the +/- value boxes the mode needs.
void TaskDimension::onTolTypeChanged()
{
    const int mode = ui->comboTolType->currentIndex();
    const bool basic = (mode == 3);
    const bool equal = (mode == 1);

    if (mode == 0) {
        // Nominal: no tolerance at all
        ui->qsbOvertolerance->setValue(0.0);
        ui->qsbUndertolerance->setValue(0.0);
    }

    // Drive the underlying checkboxes; their slots update the feature and handle
    // enable/min/under=-over bookkeeping. Qt only emits when the state actually
    // changes, so also write the flags directly to cover the no-change case.
    ui->cbTheoreticallyExact->setChecked(basic);
    ui->cbEqualTolerance->setChecked(equal);
    if (!m_dimensionVP.expired()) {
        auto* df = m_parent->getDimFeat();
        df->TheoreticalExact.setValue(basic);
        df->EqualTolerance.setValue(equal);
    }

    updateToleranceModeUi(mode);
    recomputeFeature();
}

void TaskDimension::updateToleranceModeUi(int mode)
{
    const bool showOver  = (mode == 1 || mode == 2);  // symmetric or plus-minus
    const bool showUnder = (mode == 2);               // plus-minus only

    ui->label_2->setVisible(showOver);
    ui->qsbOvertolerance->setVisible(showOver);
    ui->label_8->setVisible(showUnder);
    ui->qsbUndertolerance->setVisible(showUnder);

    if (mode == 1)
        ui->label_2->setText(QString::fromUtf8("Tolerance \xC2\xB1"));  // ±
    else
        ui->label_2->setText(tr("Upper (+)"));
    ui->label_8->setText(QString::fromUtf8("Lower (\xE2\x88\x92)"));      // −

    // The dropdown replaces these controls, and the printf-format rows are
    // hidden so the panel reads like Creo's simple tolerance box.
    ui->cbTheoreticallyExact->setVisible(false);
    ui->cbEqualTolerance->setVisible(false);
    ui->label->setVisible(false);
    ui->leFormatSpecifierOverTolerance->setVisible(false);
    ui->label_12->setVisible(false);
    ui->leFormatSpecifierUnderTolerance->setVisible(false);
    ui->cbArbitraryTolerances->setVisible(false);
}

void TaskDimension::onFormatSpecifierChanged()
{
    m_parent->getDimFeat()->FormatSpec.setValue(ui->leFormatSpecifier->text().toUtf8().constData());
    recomputeFeature();
}

void TaskDimension::onArbitraryChanged()
{
    auto* dim = m_parent->getDimFeat();
    const bool on = ui->cbArbitrary->isChecked();
    dim->Arbitrary.setValue(on);
    // Show/hide the dedicated value box only while "Edit value" is ticked.
    ui->leEditValue->setVisible(on);
    ui->labelEditValue->setVisible(on);
    if (on) {
        // Prefill with the current plain value (no unit) so the user just edits
        // a number. ONLY this box drives the shown value; the Format specifier /
        // Prefix / Suffix fields are deliberately left untouched.
        QString s = QString::number(dim->getDimValue(), 'f', ui->sbNumDecimals->value());
        ui->leEditValue->blockSignals(true);
        ui->leEditValue->setText(s);
        ui->leEditValue->blockSignals(false);
        dim->FormatSpec.setValue(s.toUtf8().constData());
    }
    else {
        // Back to the model-computed value: restore the format shown in the
        // Format-specifier field (default "%.2w" = value only, no unit).
        std::string fmt = ui->leFormatSpecifier->text().toUtf8().constData();
        if (fmt.empty()) {
            fmt = "%.2w";
        }
        dim->FormatSpec.setValue(fmt.c_str());
    }
    recomputeFeature();
}

void TaskDimension::onEditValueChanged()
{
    // The dedicated box is the ONLY writer of the override value. It sets the
    // FormatSpec directly to the typed text and never touches the other fields.
    if (!ui->cbArbitrary->isChecked()) {
        return;
    }
    auto* dim = m_parent->getDimFeat();
    dim->FormatSpec.setValue(ui->leEditValue->text().toUtf8().constData());
    recomputeFeature();
}

void TaskDimension::onFormatSpecifierOverToleranceChanged()
{
//    Base::Console().message("TD::onFormatSpecifierOverToleranceChanged()\n");
    // if (m_blockToleranceLoop) { return; }
    m_parent->getDimFeat()->FormatSpecOverTolerance.setValue(ui->leFormatSpecifierOverTolerance->text().toUtf8().constData());
    if (ui->cbArbitraryTolerances->isChecked() ) {
        // Don't do anything else if tolerance is Arbitrary
        recomputeFeature();
        return;
    }

    if (ui->cbEqualTolerance->isChecked()) {
        // the under tolerance has to match this one
        ui->leFormatSpecifierUnderTolerance->setText(ui->leFormatSpecifierOverTolerance->text());
        m_parent->getDimFeat()->FormatSpecUnderTolerance.setValue(ui->leFormatSpecifierUnderTolerance->text().toUtf8().constData());
    }
    recomputeFeature();
}

void TaskDimension::onFormatSpecifierUnderToleranceChanged()
{
//    Base::Console().message("TD::onFormatSpecifierUnderToleranceChanged()\n");
    m_parent->getDimFeat()->FormatSpecUnderTolerance.setValue(ui->leFormatSpecifierUnderTolerance->text().toUtf8().constData());
    if (ui->cbArbitraryTolerances->isChecked() ) {
        // Don't do anything else if tolerance is Arbitrary
        recomputeFeature();
        return;
    }
    if (ui->cbEqualTolerance->isChecked()) {
        // if EqualTolerance is checked, then underTolerance is disabled, so this shouldn't happen!
        // the over tolerance has to match this one
        ui->leFormatSpecifierOverTolerance->setText(ui->leFormatSpecifierUnderTolerance->text());
        m_parent->getDimFeat()->FormatSpecOverTolerance.setValue(ui->leFormatSpecifierOverTolerance->text().toUtf8().constData());
    }
    recomputeFeature();
}

void TaskDimension::onArbitraryTolerancesChanged()
{
    m_parent->getDimFeat()->ArbitraryTolerances.setValue(ui->cbArbitraryTolerances->isChecked());
    recomputeFeature();
}

void TaskDimension::onFlipArrowheadsChanged()
{
    if (m_dimensionVP.expired()) {
        return;
    }
    m_dimensionVP->FlipArrowheads.setValue(ui->cbArrowheads->isChecked());
    recomputeFeature();
}

void TaskDimension::onColorChanged()
{
    if (m_dimensionVP.expired()) {
        return;
    }
    Base::Color ac;
    ac.setValue<QColor>(ui->dimensionColor->color());
    m_dimensionVP->Color.setValue(ac);
    recomputeFeature();
}

void TaskDimension::onFontsizeChanged()
{
    if (m_dimensionVP.expired()) {
        return;
    }
    m_dimensionVP->Fontsize.setValue(ui->qsbFontSize->value().getValue());
    recomputeFeature();
}

void TaskDimension::onDrawingStyleChanged()
{
    if (m_dimensionVP.expired()) {
        return;
    }
    m_dimensionVP->StandardAndStyle.setValue(ui->comboDrawingStyle->currentIndex());
    recomputeFeature();
}

void TaskDimension::onOverrideToggled()
{
    m_parent->getDimFeat()->AngleOverride.setValue(ui->rbOverride->isChecked());
    recomputeFeature();

}

void TaskDimension::onDimAngleChanged()
{
    m_parent->getDimFeat()->LineAngle.setValue(ui->dsbDimAngle->value());
    recomputeFeature();
}

void TaskDimension::onExtAngleChanged()
{
    m_parent->getDimFeat()->ExtensionAngle.setValue(ui->dsbExtAngle->value());
    recomputeFeature();
}

void TaskDimension::onDimUseDefaultClicked()
{
    pointPair points = m_parent->getDimFeat()->getLinearPoints();
    //duplicate coordinate conversion logic from QGIViewDimension
    Base::Vector2d first2(points.first().x, -points.first().y);
    Base::Vector2d second2(points.second().x, -points.second().y);
    double lineAngle = (second2 - first2).Angle();
    ui->dsbDimAngle->setValue(Base::toDegrees(lineAngle));
}

void TaskDimension::onDimUseSelectionClicked()
{
    std::pair<double, bool> result = getAngleFromSelection();
    if (result.second) {
        ui->dsbDimAngle->setValue(Base::toDegrees(result.first));
    }
}

void TaskDimension::onExtUseDefaultClicked()
{
    pointPair points = m_parent->getDimFeat()->getLinearPoints();
    //duplicate coordinate conversion logic from QGIViewDimension
    Base::Vector2d first2(points.first().x, -points.first().y);
    Base::Vector2d second2(points.second().x, -points.second().y);
    Base::Vector2d lineDirection = second2 - first2;
    Base::Vector2d extensionDirection(-lineDirection.y, lineDirection.x);
    double extensionAngle = extensionDirection.Angle();
    ui->dsbExtAngle->setValue(Base::toDegrees(extensionAngle));
}
void TaskDimension::onExtUseSelectionClicked()
{
    std::pair<double, bool> result = getAngleFromSelection();
    if (result.second) {
        ui->dsbExtAngle->setValue(Base::toDegrees(result.first));
    }
}

std::pair<double, bool> TaskDimension::getAngleFromSelection()
{
    std::pair<double, bool> result;
    result.first = 0.0;
    result.second = true;
    std::vector<Gui::SelectionObject> selection = Gui::Selection().getSelectionEx();
    TechDraw::DrawViewPart * objFeat = nullptr;
    std::vector<std::string> SubNames;
    if (!selection.empty()) {
        objFeat = static_cast<TechDraw::DrawViewPart*> (selection.front().getObject());
        SubNames = selection.front().getSubNames();
        if (SubNames.size() == 2) {             //expecting Vertices
            std::string geomName0 = DrawUtil::getGeomTypeFromName(SubNames[0]);
            int geomIndex0 = DrawUtil::getIndexFromName(SubNames[0]);
            std::string geomName1 = DrawUtil::getGeomTypeFromName(SubNames[1]);
            int geomIndex1 = DrawUtil::getIndexFromName(SubNames[1]);
            if ((geomName0 == "Vertex") && (geomName1 == "Vertex"))  {
                TechDraw::VertexPtr v0 = objFeat->getProjVertexByIndex(geomIndex0);
                TechDraw::VertexPtr v1 = objFeat->getProjVertexByIndex(geomIndex1);
                Base::Vector2d v02(v0->point().x, -v0->point().y);
                Base::Vector2d v12(v1->point().x, -v1->point().y);
                result.first = (v12 - v02).Angle();
                return result;
            }
        } else if (SubNames.size() == 1) {      //expecting Edge
            std::string geomName0 = DrawUtil::getGeomTypeFromName(SubNames[0]);
            int geomIndex0 = DrawUtil::getIndexFromName(SubNames[0]);
            if (geomName0 == "Edge") {
                TechDraw::BaseGeomPtr edge = objFeat->getGeomByIndex(geomIndex0);
                Base::Vector2d v02(edge->getStartPoint().x, -edge->getStartPoint().y);
                Base::Vector2d v12(edge->getEndPoint().x, -edge->getEndPoint().y);
                result.first = (v12 - v02).Angle();
                return result;
            }
        }
    }

    QMessageBox::warning(Gui::getMainWindow(), QObject::tr("Incorrect Selection"),
                                               QObject::tr("Select 2 vertices or 1 edge"));
    result.second = false;
    return result;
}

/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
TaskDlgDimension::TaskDlgDimension(QGIViewDimension *parent, ViewProviderDimension *dimensionVP) :
    TaskDialog()
{
    widget  = new TaskDimension(parent, dimensionVP);
    taskbox = new Gui::TaskView::TaskBox(Gui::BitmapFactory().pixmap("TechDraw_Dimension"), widget->windowTitle(), true, nullptr);
    taskbox->groupLayout()->addWidget(widget);
    Content.push_back(taskbox);
    setAutoCloseOnTransactionChange(true);
}

TaskDlgDimension::~TaskDlgDimension()
{
}

void TaskDlgDimension::update()
{
}

//==== calls from the TaskView ===============================================================
void TaskDlgDimension::open()
{
}

void TaskDlgDimension::clicked(int i)
{
    Q_UNUSED(i);
}

bool TaskDlgDimension::accept()
{
    widget->accept();
    return true;
}

bool TaskDlgDimension::reject()
{
    widget->reject();
    return true;
}

#include "moc_TaskDimension.cpp"
