import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class TeamBoardPlugin extends Plugin {
    static id = "teamBoardPlugin";
    
    resources = {
        remove_disabled_reason_providers: (el) => {
            if (this.isLastTimelineItem(el)) {
                return _t("You cannot remove the last item.");
            }
        },
        dropzone_selectors: {
            selector: ".s_team_board",
            excludeAncestor: ".s_team_board, .s_table_of_content, .s_table_of_content_content, .s_popup, .o_popup_modal, .modal",
        },
    }

    isLastTimelineItem(el) {
        const container = el.closest('.container');
        if (!container){
            return false;
        }
        const cards = Array.from(container.querySelectorAll(".o_team_board_card"));
        return cards.length <= 1;
    }
}

registry.category("website-plugins").add(TeamBoardPlugin.id, TeamBoardPlugin);
