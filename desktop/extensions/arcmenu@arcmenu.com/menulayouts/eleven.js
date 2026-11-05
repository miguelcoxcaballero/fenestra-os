import {createWindowsPower} from './windowsPower.js';
import {populateHome} from './windowsStartHome.js';
import {pick, onSchemeChanged} from '../fenestraTheme.js';
import Clutter from 'gi://Clutter';
import GObject from 'gi://GObject';
import Shell from 'gi://Shell';
import St from 'gi://St';

import {ArcMenuManager} from '../arcmenuManager.js';
import {BaseMenuLayout} from './baseMenuLayout.js';
import * as Constants from '../constants.js';
import {IconGrid} from '../iconGrid.js';
import * as MW from '../menuWidgets.js';
import {getOrientationProp} from '../utils.js';

import {gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

export class Layout extends BaseMenuLayout {
    static {
        GObject.registerClass(this);
    }

    constructor(menuButton) {
        super(menuButton, {
            display_type: Constants.DisplayType.GRID,
            search_display_type: Constants.DisplayType.GRID,
            search_results_spacing: 5,
            context_menu_location: Constants.ContextMenuLocation.BOTTOM_CENTERED,
            column_spacing: 0,
            row_spacing: 0,
            ...getOrientationProp(true),
            default_menu_width: 832,
        });

        this.iconSizeCategories = Constants.IconSizes.LARGE;
        this.iconSizeApps = Constants.IconSizes.LARGE;
        this.iconSizeShortcuts = Constants.IconSizes.SMALL;
        this.iconSizeButtons = Constants.IconSizes.SMALL;
        this.iconSizePinnedApps = Constants.IconSizes.LARGE;

        this.connect('button-press-event', (actor, event) => {
            if (this.backButton.visible && event.get_button() === 8)
                this.backButton.activate(event);
        });

        this.searchEntry.style = 'margin: 5px 15px 10px 15px;';

        this._mainBox = new St.BoxLayout({
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.FILL,
            ...getOrientationProp(true),
        });
        this.add_child(this._mainBox);

        const navButtonsStyle = 'padding: 0px 20px 10px 25px;';
        this.backButton = this._createNavigationRow(_('All Apps'), Constants.Direction.GO_PREVIOUS,
            _('Back'), () => this.setDefaultMenuView());
        this.backButton.set({
            style: navButtonsStyle,
            visible: false,
        });
        this._mainBox.add_child(this.backButton);

        this.allAppsButton = this._createNavigationRow(_('Pinned'), Constants.Direction.GO_NEXT,
            _('All Apps'), () => this.displayAllApps());
        this.allAppsButton.set({
            style: navButtonsStyle,
            visible: false,
        });
        this._mainBox.add_child(this.allAppsButton);

        this.frequentAppsHeader = this.createLabelRow(_('Frequent'));

        this.frequentAppsHeader.label.y_align = Clutter.ActorAlign.CENTER;
        this.frequentAppsHeader.style = 'padding: 10px 20px;';

        const topBox = new St.BoxLayout({
            x_expand: false,
            y_expand: false,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.START,
            ...getOrientationProp(false),
        });
        topBox.add_child(this.searchEntry);
        // Windows 11: the search pill sits on the menu's own acrylic (no header
        // band or separator, in light and dark mode; only the footer is tinted).
        // Same 58 px height as before.
        const headerStyle = () => 'background-color: transparent; padding: 16px 32px 8px;';
        topBox.style = headerStyle();
        onSchemeChanged(this, () => {
            topBox.style = headerStyle(); this.updateStyle(); this._homeDirty = true;
            if (!this.arcMenu.isOpen) this.setDefaultMenuView();
        });
        topBox.x_expand = true;
        this.insert_child_at_index(topBox, 0);

        this.applicationsBox = new St.BoxLayout({
            ...getOrientationProp(true),
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.FILL,
            style: 'padding-bottom: 10px; spacing: 8px;',
            style_class: 'arcmenu-margin-box',
        });
        this.applicationsScrollBox = this._createScrollView({
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.START,
            style_class: this._disableFadeEffect ? '' : 'vfade',
        });
        this._addChildToParent(this.applicationsScrollBox, this.applicationsBox);
        this._mainBox.add_child(this.applicationsScrollBox);

        this.actionsContainerBox = new St.BoxLayout({
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.END,
            ...getOrientationProp(false),
        });
        this._mainBox.add_child(this.actionsContainerBox);

        this.actionsBox = new St.BoxLayout({
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.CENTER,
            ...getOrientationProp(false),
        });
        this.actionsBox.style = 'spacing: 10px;';
        // Windows 11 footer band: same tint as the header, 64 px tall.
        this.actionsContainerBox.style = `background-color: ${pick('rgba(0,0,0,0.25)', 'rgba(0,0,0,0.04)')}; border-top: 1px solid ${pick('rgba(0,0,0,0.2)', 'rgba(0,0,0,0.06)')}; padding: 0px 52px 0px 48px; min-height: 64px;`;
        this.actionsContainerBox.add_child(this.actionsBox);

        this.shortcutsBox = new St.BoxLayout({
            x_expand: true,
            y_expand: true,
            x_align: Clutter.ActorAlign.FILL,
            y_align: Clutter.ActorAlign.CENTER,
            ...getOrientationProp(true),
            style: 'padding: 0px 25px;',
        });

        this.shortcutsGrid = new IconGrid({
            halign: Clutter.ActorAlign.FILL,
            column_spacing: 10,
            row_spacing: 5,
            force_columns: 2,
        });
        this.shortcutsBox.add_child(this.shortcutsGrid);

        this.applicationsGrid.layout_manager.set({
            force_columns: 1,
            column_spacing: 5,
            row_spacing: 5,
        });
        this.applicationsGrid.halign = Clutter.ActorAlign.FILL;

        ArcMenuManager.settings.connectObject('changed::eleven-layout-extra-shortcuts', () => this._createExtraButtons(), this);
        ArcMenuManager.settings.connectObject('changed::eleven-show-frequent-apps', () => this.setDefaultMenuView(), this);

        this._createExtraButtons();
        this.updateStyle();
        this.updateWidth();
        this.loadCategories();
        this.loadPinnedApps();
        this.setDefaultMenuView();
        this._connectAppChangedEvents();
    }

    _createExtraButtons() {
        this.actionsBox.destroy_all_children();

        const avatarMenuItem = new MW.AvatarMenuItem(this, Constants.DisplayType.LIST);
        // Windows: the hover highlight hugs avatar + name, it is not full width.
        avatarMenuItem.x_expand = false;
        avatarMenuItem.y_expand = false;
        avatarMenuItem.x_align = Clutter.ActorAlign.START;
        avatarMenuItem.y_align = Clutter.ActorAlign.CENTER;
        avatarMenuItem.style = 'padding: 4px 12px 4px 8px; spacing: 12px; border-radius: 4px; min-height: 0px;';
        avatarMenuItem.label.style = 'font-family: Segoe UI; font-size: 12px; font-weight: normal;';
        // Windows shows the account's first + last name only.
        const shortName = () => { const w = avatarMenuItem.label.text.trim().split(/\s+/); if (w.length > 2) avatarMenuItem.label.text = w.slice(0, 2).join(' '); };
        avatarMenuItem.label.connect('notify::text', shortName); shortName();
        this.actionsBox.add_child(avatarMenuItem);

        const isContainedInCategory = false;
        const extraButtons = ArcMenuManager.settings.get_value('eleven-layout-extra-shortcuts').deep_unpack();

        for (let i = 0; i < extraButtons.length; i++) {
            const {id} = extraButtons[i];
            if (id === Constants.ShortcutCommands.SEPARATOR) {
                const separator = new MW.ArcMenuSeparator(this, Constants.SeparatorStyle.LONG,
                    Constants.SeparatorAlignment.VERTICAL);
                separator.x_expand = false;
                this.actionsBox.add_child(separator);
            } else {
                const button = this.createMenuItem(extraButtons[i], Constants.DisplayType.BUTTON,
                    isContainedInCategory);
                if (button.shouldShow)
                    this.actionsBox.add_child(button);
                else
                    button.destroy();
            }
        }

        let leaveButton;
        leaveButton=createWindowsPower(this,avatarMenuItem);
        leaveButton.x_expand = true;
        leaveButton.x_align = Clutter.ActorAlign.END;
        leaveButton.y_align = Clutter.ActorAlign.CENTER;

        this.actionsBox.add_child(leaveButton);
    }

    loadPinnedApps() {
        this.display_type = Constants.DisplayType.GRID;
        super.loadPinnedApps();
    }

    loadFrequentApps() {
        this.frequentAppsList?.forEach(item => {
            item.destroy();
        });
        this.frequentAppsList = [];

        if (!ArcMenuManager.settings.get_boolean('eleven-show-frequent-apps'))
            return;

        const mostUsed = Shell.AppUsage.get_default().get_most_used();

        if (mostUsed.length < 1)
            return;

        const pinnedApps = ArcMenuManager.settings.get_value('pinned-apps').deepUnpack();
        const pinnedAppsIds = pinnedApps.map(item => item.id);

        for (let i = 0; i < mostUsed.length; i++) {
            if (!mostUsed[i])
                continue;

            const appInfo = mostUsed[i].get_app_info();
            if (appInfo.should_show() && !pinnedAppsIds.includes(appInfo.get_id())) {
                const item = new MW.ApplicationMenuItem(this, mostUsed[i], Constants.DisplayType.LIST);
                this.frequentAppsList.push(item);
            }
        }

        const MaxItems = 8;
        if (this.frequentAppsList.length > MaxItems)
            this.frequentAppsList.splice(MaxItems);
    }

    setDefaultMenuView() {
        this.setGridLayout(Constants.DisplayType.GRID, 0);
        super.setDefaultMenuView();
        this.displayPinnedApps();
    }

    _clearActorsFromBox(box) {
        super._clearActorsFromBox(box);
    }

    displayAllApps() {
        this.setGridLayout(Constants.DisplayType.LIST, 5);
        super.displayAllApps();
        this.setGridLayout(Constants.DisplayType.GRID, 0, false);
    }

    updateStyle() {
        const themeNode = this.arcMenu.box.get_theme_node();
        let borderRadius = themeNode.get_length('border-radius');

        const scaleFactor = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        borderRadius /= scaleFactor;

        const borderRadiusStyle = `border-radius: 0px 0px ${borderRadius}px ${borderRadius}px;`;
        // Windows 11 footer band: same tint as the header, 64 px tall.
        const style = `margin: 0px; spacing: 0px; background-color: ${pick('rgba(0,0,0,0.21)', 'rgba(0,0,0,0.03)')}; padding: 0px 55px 6px 56px;
                       min-height: 58px; border-color: ${pick('rgba(0,0,0,0.2)', 'rgba(0,0,0,0.06)')}; border-top-width: 1px;`;

        this.actionsContainerBox.style = style + borderRadiusStyle;
        // No top padding either: it left a strip of plain menu background above the search box.
        this.arcMenu.box.style = 'padding: 0px; font-family: Segoe UI; font-size: 14px;';
    }

    setGridLayout(displayType, spacing, setStyle = true) {
        if (setStyle) {
            if (displayType === Constants.DisplayType.LIST)
                this.applicationsScrollBox.style_class = this._disableFadeEffect ? '' : 'small-vfade';
            else
                this.applicationsScrollBox.style_class = this._disableFadeEffect ? '' : 'vfade';
            this.applicationsGrid.halign = displayType === Constants.DisplayType.LIST ? Clutter.ActorAlign.FILL
                : Clutter.ActorAlign.CENTER;
        }

        this.applicationsGrid.layout_manager.column_spacing = spacing;
        this.applicationsGrid.layout_manager.row_spacing = spacing;
        this.display_type = displayType;
    }

    loadCategories() {
        this.display_type = Constants.DisplayType.LIST;
        this.categoryDirectories = null;
        this.categoryDirectories = new Map();
        this.hasPinnedApps = true;
        super.loadCategories();
    }

    displayPinnedApps() {
        super.displayPinnedApps();
        populateHome(this);
    }

    _displayAppList(apps, category, grid) {
        super._displayAppList(apps, category, grid);

        this._hideNavigationButtons();

        if (category === Constants.CategoryType.HOME_SCREEN || category === Constants.CategoryType.PINNED_APPS) {
            this.allAppsButton.visible = true;
            if (!this.applicationsBox.contains(this.frequentAppsHeader))
                this.applicationsBox.insert_child_at_index(this.frequentAppsHeader, 2);
        } else if (category === Constants.CategoryType.ALL_PROGRAMS) {
            this.backButton.visible = true;
        }
    }

    _hideNavigationButtons() {
        this.allAppsButton.visible = false;
        this.backButton.visible = false;
    }

    _onSearchEntryChanged(searchEntry, searchString) {
        if (!searchEntry.isEmpty())
            this._hideNavigationButtons();
        super._onSearchEntryChanged(searchEntry, searchString);
    }

    _onDestroy() {
        this._startGeneration = (this._startGeneration ?? 0) + 1;
        for (const actor of this._startOwned ?? []) actor.destroy();
        this._startOwned = [];
        if (this.arcMenu)
            this.arcMenu.box.style = null;

        this.frequentAppsList?.forEach(item => {
            item.destroy();
        });
        this.backButton.destroy();
        this.allAppsButton.destroy();

        super._onDestroy();
    }
}
