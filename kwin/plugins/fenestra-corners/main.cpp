// SPDX-License-Identifier: GPL-3.0-or-later
#include "corners.h"

namespace KWin
{
KWIN_EFFECT_FACTORY_SUPPORTED(CornersEffect, "metadata.json", return CornersEffect::supported();)
}

#include "main.moc"
