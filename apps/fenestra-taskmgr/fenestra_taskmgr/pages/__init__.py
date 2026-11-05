"""Page registry (imported lazily so only the start page is built at startup)."""


class _Lazy(dict):
    MODULES = {
        "processes": ("processes", "ProcessesPage"),
        "performance": ("performance", "PerformancePage"),
        "apphistory": ("apphistory", "AppHistoryPage"),
        "startup": ("startup", "StartupPage"),
        "users": ("users", "UsersPage"),
        "details": ("details", "DetailsPage"),
        "services": ("services", "ServicesPage"),
        "settings": ("settings", "SettingsPage"),
    }

    def __contains__(self, k):
        return k in self.MODULES

    def get(self, k, default=None):
        if k not in self.MODULES:
            return default
        import importlib
        mod, cls = self.MODULES[k]
        return getattr(importlib.import_module(f"fenestra_taskmgr.pages.{mod}"), cls)

    def __getitem__(self, k):
        return self.get(k)


PAGES = _Lazy()
