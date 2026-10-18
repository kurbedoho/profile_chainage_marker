# -*- coding: utf-8 -*-


def classFactory(iface):
    from .profile_chainage_marker import ProfileChainageMarkerPlugin

    return ProfileChainageMarkerPlugin(iface)
