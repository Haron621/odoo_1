import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { BuilderAction } from "@html_builder/core/builder_action";
import { withSequence } from "@html_editor/utils/resource";


export class AnotherTeamBoardPlugin extends Plugin {
    static id = "anotherTeamBoardPlugin";
    
    resources = {
        get_overlay_buttons: withSequence(2, {
            getButtons: this.getOverlayButtons.bind(this),
        }),
    }

    getOverlayButtons(target) {
        if (!this.isTeamBoardCard(target)) {
            return [];
        }
        return [
            {
                class: "oe_snippet_prioritize text-warning fa fa-star",
                icon: "star",
                title: _t("Prioritize"),
                handler: () => {
                    this.prioritizeCard(target);
                },
            },
        ];
    }

    isTeamBoardCard(target) {
        return Boolean(target && target.matches && target.matches(".o_team_board_card")); 
    }

    prioritizeCard(target){
        let row = target.closest('.row');
        let cards = Array.from(row.querySelectorAll(".o_team_board_card"));
        row.prepend(target);
    }
}

registry.category("website-plugins").add(AnotherTeamBoardPlugin.id, AnotherTeamBoardPlugin);
