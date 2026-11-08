// Bench stand-in: plasma-nm's sorted view of NetworkModel (here a copy of its rows).
import QtQuick
ListModel {
    id: proxy
    property var sourceModel
    onSourceModelChanged: { clear(); if (sourceModel) for (let i = 0; i < sourceModel.count; i++) append(sourceModel.get(i)) }
}
