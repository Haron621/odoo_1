import { pasteHtml, pasteOdooEditorHtml } from "@html_editor/../tests/_helpers/user_actions";

import {
    contains,
    defineMailModels,
    openDiscuss,
    start,
    startServer,
} from "@mail/../tests/mail_test_helpers";
import { getEditorFromComposerEl } from "@mail/../tests/mail_test_helpers_composer";
import { describe, expect, test } from "@odoo/hoot";
import { manuallyDispatchProgrammaticEvent, queryOne } from "@odoo/hoot-dom";
import { patch } from "@web/core/utils/patch";

describe.current.tags("desktop");
defineMailModels();

async function openComposer() {
    const pyEnv = await startServer();
    const channelId = pyEnv["discuss.channel"].create({ name: "General" });
    await start();
    await openDiscuss(channelId);
    await contains(".o-mail-Composer-html");
}

test("pasted HTML loses its inline formatting", async () => {
    await openComposer();
    pasteHtml(
        getEditorFromComposerEl(".o-mail-Composer"),
        "<b>Hello</b> <i><u>dear</u></i> <s>old</s> <strong><em>World</em></strong>"
    );
    await contains(".o-mail-Composer-html .o-paragraph:contains('World')");
    expect(".o-mail-Composer-html .o-paragraph").toHaveInnerHTML("Hello dear old World");
});

test("pasted editor HTML loses its inline formatting but keeps its links", async () => {
    await openComposer();
    pasteOdooEditorHtml(
        getEditorFromComposerEl(".o-mail-Composer"),
        `<b>Hello</b> <a href="https://www.odoo.com">Odoo</a>`
    );
    await contains(".o-mail-Composer-html .o-paragraph a:contains('Odoo')");
    expect(".o-mail-Composer-html b").toHaveCount(0);
    expect(".o-mail-Composer-html .o-paragraph").toHaveText("Hello Odoo");
});

test("dropped HTML loses its inline formatting but keeps its links", async () => {
    await openComposer();
    const paragraph = queryOne(".o-mail-Composer-html .o-paragraph");
    patch(document, {
        caretPositionFromPoint: () => ({ offsetNode: paragraph, offset: 0 }),
    });
    const dataTransfer = new DataTransfer();
    dataTransfer.setData("text/html", `<b>Hello</b><a href="https://www.odoo.com">Odoo</a>`);
    await manuallyDispatchProgrammaticEvent(paragraph, "drop", { dataTransfer });
    await contains(".o-mail-Composer-html .o-paragraph a:contains('Odoo')");
    expect(".o-mail-Composer-html b").toHaveCount(0);
    expect(".o-mail-Composer-html .o-paragraph").toHaveText("HelloOdoo");
});
