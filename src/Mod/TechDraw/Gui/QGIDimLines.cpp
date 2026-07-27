/***************************************************************************
 *   Copyright (c) 2016 WandererFan <wandererfan@gmail.com>                *
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

# include <cassert>

# include <QPainterPath>
# include <QPainterPathStroker>

#include "QGIDimLines.h"
#include "PreferencesGui.h"


using namespace TechDrawGui;
using namespace TechDraw;

QGIDimLines::QGIDimLines()
{
    setCacheMode(QGraphicsItem::NoCache);
    setAcceptHoverEvents(false);
    setFlag(QGraphicsItem::ItemIsSelectable, false);
    setFlag(QGraphicsItem::ItemIsMovable, false);
    setWidth(0.5);
}

void QGIDimLines::draw()
{
}

void QGIDimLines::setUngappedPath(const QPainterPath& p)
{
    // Keep the full base path, and show it un-gapped by default. The page's
    // dimension-line-break pass will replace the displayed path with a gapped
    // version derived from this base.
    m_ungapped = p;
    setPath(p);
}

QPainterPath QGIDimLines::shape() const
{
    QPainterPath outline;
    QPainterPathStroker stroker;
    stroker.setWidth(getEdgeFuzz());
    outline = stroker.createStroke(path());
    return outline;
}

double QGIDimLines::getEdgeFuzz() const
{
    return PreferencesGui::edgeFuzz();
}


QRectF QGIDimLines::boundingRect() const
{
    return shape().controlPointRect().adjusted(-3, -3, 3, 3);
}
