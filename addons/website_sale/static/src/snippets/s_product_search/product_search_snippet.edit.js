import { registry } from '@web/core/registry';
import { ProductSearchSnippet } from './product_search_snippet';

const ProductSearchSnippetEdit = (I) => class extends I {
    // Keep the filters of the unavailable attributes visible, so that they can be removed
    hideUnavailableFilter() {}

    getConfigurationSnapshot() {
        const snapshot = JSON.parse(super.getConfigurationSnapshot() || '{}');
        snapshot.attributeIds = this.getAttributeIds();
        return JSON.stringify(snapshot);
    }

    isImpactedBy(el) {
        // Re-render the menu items when an attribute filter is added or changed
        return this.el.contains(el);
    }

    onClickSearch() {}
};

registry
    .category('public.interactions.edit')
    .add('website_sale.product_search_snippet', {
        Interaction: ProductSearchSnippet,
        mixin: ProductSearchSnippetEdit,
    });
