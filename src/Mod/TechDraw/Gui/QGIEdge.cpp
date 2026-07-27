/***************************************************************************
 *   Copyright (c) 2013 Luke Parry <l.parry@warwick.ac.uk>                 *
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


# include <QGraphicsSceneMouseEvent>
# include <QLineF>
# include <QPainterPath>
# include <QPainterPathStroker>
# include <QTimer>


#include <App/Application.h>
#include <App/Document.h>
#include <App/Material.h>
#include <Base/Console.h>
#include <Base/Parameter.h>
#include <Base/Vector3D.h>
#include <Gui/Control.h>
#include <Mod/TechDraw/App/Cosmetic.h>
#include <Mod/TechDraw/App/CosmeticVertex.h>
#include <Mod/TechDraw/App/DrawUtil.h>
#include <Mod/TechDraw/App/DrawViewPart.h>

#include "QGIEdge.h"
#include "PreferencesGui.h"
#include "Rez.h"
#include "TaskLineDecor.h"
#include "QGIView.h"

using namespace TechDrawGui;
using namespace TechDraw;

QGIEdge::QGIEdge(int index) :
    projIndex(index),
    isCosmetic(false),
    isHiddenEdge(false),
    isSmoothEdge(false)
{
    setFlag(QGraphicsItem::ItemIsFocusable, true);      // to get key press events
    setFlag(QGraphicsItem::ItemIsSelectable, true);

    setWidth(1.0);
    setCosmetic(isCosmetic);
    setFill(Qt::NoBrush);
}

// NOTE this refers to Qt cosmetic lines (a line with minimum width),
// not FreeCAD cosmetic lines
void QGIEdge::setCosmetic(bool state)
{
    isCosmetic = state;
    if (state) {
        setWidth(0.0);
    }
}

void QGIEdge::setHiddenEdge(bool b) {
    isHiddenEdge = b;
}

void QGIEdge::setPrettyNormal() {
    if (isHiddenEdge) {
        m_pen.setColor(getHiddenColor());
        return;
    }
    QGIPrimPath::setPrettyNormal();
}

QColor QGIEdge::getHiddenColor()
{
    Base::Color fcColor = Base::Color((uint32_t) Preferences::getPreferenceGroup("Colors")->GetUnsigned("HiddenColor", 0x000000FF));
    return PreferencesGui::getAccessibleQColor(fcColor.asValue<QColor>());
}


 double QGIEdge::getEdgeFuzz() const
{
    return PreferencesGui::edgeFuzz();
}


QRectF QGIEdge::boundingRect() const
{
    return shape().controlPointRect();
}

QPainterPath QGIEdge::shape() const
{
    QPainterPath outline;
    QPainterPathStroker stroker;
    stroker.setWidth(getEdgeFuzz());
    outline = stroker.createStroke(path());
    return outline;
}

void QGIEdge::mouseDoubleClickEvent(QGraphicsSceneMouseEvent *event)
{
    Q_UNUSED(event)
    auto* parent = dynamic_cast<QGIView *>(parentItem());
    if (parent && parent->getViewObject() && parent->getViewObject()->isDerivedFrom<TechDraw::DrawViewPart>()) {
        auto* baseFeat = static_cast<TechDraw::DrawViewPart *>(parent->getViewObject());
        std::vector<std::string> edgeName(1, DrawUtil::makeGeomName("Edge", getProjIndex()));

        Gui::Control().showDialog(new TaskDlgLineDecor(baseFeat, edgeName));
    }
}

void QGIEdge::setLinePen(const QPen& linePen)
{
    m_pen = linePen;
}

// ANVIL CAD: a cosmetic edge is "stretchable" only if it is a single straight
// segment (moveTo + lineTo). This excludes cosmetic circles/arcs such as the
// PCD pitch circle, so only the radial center-line ticks can be dragged.
bool QGIEdge::isStretchableCosmeticLine(QPointF& p0, QPointF& p1) const
{
    if (m_source != TechDraw::SourceType::COSMETICEDGE) {
        return false;
    }
    const QPainterPath pp = path();
    if (pp.elementCount() != 2) {
        return false;
    }
    QPainterPath::Element e0 = pp.elementAt(0);
    QPainterPath::Element e1 = pp.elementAt(1);
    if (!e1.isLineTo()) {
        return false;
    }
    p0 = QPointF(e0.x, e0.y);
    p1 = QPointF(e1.x, e1.y);
    return true;
}

// ANVIL CAD: begin a drag-to-extend of an already-selected straight center line.
// The line grows symmetrically about its midpoint: both ends move outward by the
// same amount as the cursor is dragged along the axis. We accept the event so the
// parent view is not dragged instead.
void QGIEdge::mousePressEvent(QGraphicsSceneMouseEvent *event)
{
    QPointF p0, p1;
    if (event->button() == Qt::LeftButton && isSelected()
        && isStretchableCosmeticLine(p0, p1)) {
        QPointF center = (p0 + p1) / 2.0;
        double half = QLineF(center, p1).length();   // half the full length
        // the grabbed end (nearer the cursor) defines the positive axis direction
        double d0 = QLineF(event->pos(), p0).length();
        double d1 = QLineF(event->pos(), p1).length();
        QPointF grabbed = (d0 <= d1) ? p0 : p1;
        double gl = QLineF(center, grabbed).length();
        if (half > 1.0e-6 && gl > 1.0e-6) {
            m_center = center;
            m_axis = (grabbed - center) / gl;   // unit vector toward grabbed end
            m_halfLen = half;
            m_endA = center + m_axis * half;
            m_endB = center - m_axis * half;
            m_pressPos = event->pos();
            m_stretching = true;
            event->accept();
            return;
        }
    }
    QGIPrimPath::mousePressEvent(event);
}

void QGIEdge::mouseMoveEvent(QGraphicsSceneMouseEvent *event)
{
    if (m_stretching) {
        QPointF drag = event->pos() - m_pressPos;
        double s = drag.x() * m_axis.x() + drag.y() * m_axis.y();  // project onto axis
        double newHalf = m_halfLen + s;
        if (newHalf < 1.0) {
            newHalf = 1.0;   // keep a minimum visible length (scene units)
        }
        m_endA = m_center + m_axis * newHalf;   // both ends move out equally
        m_endB = m_center - m_axis * newHalf;
        QPainterPath np;
        np.moveTo(m_endB);
        np.lineTo(m_endA);
        setPath(np);
        event->accept();
        return;
    }
    QGIPrimPath::mouseMoveEvent(event);
}

void QGIEdge::mouseReleaseEvent(QGraphicsSceneMouseEvent *event)
{
    if (m_stretching) {
        m_stretching = false;
        persistStretch();
        event->accept();
        return;
    }
    QGIPrimPath::mouseReleaseEvent(event);
}

// ANVIL CAD: write the new endpoints back to the cosmetic edge. Item coordinates
// map directly onto the geometry (getStartPoint) space, so the same
// makeCanonicalPointInverted() conversion used by the Extend/Shorten Line
// command applies here.
void QGIEdge::persistStretch()
{
    auto* parent = dynamic_cast<QGIView*>(parentItem());
    if (!parent || !parent->getViewObject()
        || !parent->getViewObject()->isDerivedFrom<TechDraw::DrawViewPart>()) {
        return;
    }
    auto* dvp = static_cast<TechDraw::DrawViewPart*>(parent->getViewObject());
    TechDraw::BaseGeomPtr geom = dvp->getGeomByIndex(getProjIndex());
    if (!geom || geom->source() != TechDraw::SourceType::COSMETICEDGE) {
        return;
    }
    std::string tag = geom->getCosmeticTag();
    TechDraw::CosmeticEdge* oldCE = dvp->getCosmeticEdge(tag);
    if (!oldCE) {
        return;
    }
    TechDraw::LineFormat savedFormat = oldCE->m_format;   // preserve dashed style etc.

    // Item/scene coords are Rez::guiX(geometry); convert back to geometry (app)
    // space with Rez::appX before mapping to stored (canonical) coords, else the
    // saved line is multiplied by the Rez factor and shoots off the sheet.
    Base::Vector3d endACanon =
        TechDraw::CosmeticVertex::makeCanonicalPointInverted(
            dvp, Base::Vector3d(Rez::appX(m_endA.x()), Rez::appX(m_endA.y()), 0.0));
    Base::Vector3d endBCanon =
        TechDraw::CosmeticVertex::makeCanonicalPointInverted(
            dvp, Base::Vector3d(Rez::appX(m_endB.x()), Rez::appX(m_endB.y()), 0.0));

    App::Document* doc = dvp->getDocument();
    if (doc) {
        doc->openTransaction("Stretch center line");
    }
    std::vector<std::string> toDelete(1, tag);
    dvp->removeCosmeticEdge(toDelete);
    std::string newTag = dvp->addCosmeticEdge(endBCanon, endACanon);
    TechDraw::CosmeticEdge* newCE = dvp->getCosmeticEdge(newTag);
    if (newCE) {
        newCE->m_format = savedFormat;
    }
    if (doc) {
        doc->commitTransaction();
    }

    // Rebuilding the view deletes this very QGIEdge, so defer it until after we
    // have returned from the mouse-release event.
    QTimer::singleShot(0, [dvp]() {
        dvp->refreshCEGeoms();
        dvp->requestPaint();
    });
}

