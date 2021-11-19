# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime
from werkzeug.exceptions import Forbidden, NotFound

from odoo import fields, http, tools, _
from odoo.http import request
from odoo.addons.base.models.ir_qweb_fields import nl2br
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.payment.controllers.portal import PaymentProcessing
from odoo.addons.website.controllers.main import QueryURL
from odoo.addons.website.models.ir_http import sitemap_qs2dom
from odoo.exceptions import ValidationError
from odoo.addons.website.controllers.main import Website
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.osv import expression

_log = logging.getLogger("__---___--->> [%s] :: " % __name__)


class TableCompute(object):

    def __init__(self):
        self.table = {}

    def _check_place(self, posx, posy, sizex, sizey, ppr):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx + x >= ppr:
                    res = False
                    break
                row = self.table.setdefault(posy + y, {})
                if row.setdefault(posx + x) is not None:
                    res = False
                    break
            for x in range(ppr):
                self.table[posy + y].setdefault(x, None)
        return res

    def process(self, products, ppg=20, ppr=4):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        x = 0
        for p in products:
            x = min(max(p.website_size_x, 1), ppr)
            y = min(max(p.website_size_y, 1), ppr)
            if index >= ppg:
                x = y = 1

            pos = minpos
            while not self._check_place(pos % ppr, pos // ppr, x, y, ppr):
                pos += 1
            # if 21st products (index 20) and the last line is full (ppr products in it), break
            # (pos + 1.0) / ppr is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= ppg and ((pos + 1.0) // ppr) > maxy:
                break

            if x == 1 and y == 1:   # simple heuristic for CPU optimization
                minpos = pos // ppr

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos // ppr) + y2][(pos % ppr) + x2] = False
            self.table[pos // ppr][pos % ppr] = {
                'product': p, 'x': x, 'y': y,
                'ribbon': p.website_ribbon_id,
            }
            if index <= ppg:
                maxy = max(maxy, y + (pos // ppr))
            index += 1

        # Format table according to HTML needs
        rows = sorted(self.table.items())
        rows = [r[1] for r in rows]
        for col in range(len(rows)):
            cols = sorted(rows[col].items())
            x += len(cols)
            rows[col] = [r[1] for r in cols if r[1]]

        return rows


class WebsiteLines(WebsiteSale):

    def sitemap_shop(env, rule, qs):
        if not qs or qs.lower() in '/shop':
            yield {'loc': '/shop'}

        Category = env['product.public.category']
        dom = sitemap_qs2dom(qs, '/shop/category', Category._rec_name)
        dom += env['website'].get_current_website().website_domain()
        for cat in Category.search(dom):
            loc = '/shop/category/%s' % slug(cat)
            if not qs or qs.lower() in loc:
                yield {'loc': loc}

    def _get_search_domain(self, search, category, attrib_values):
        domain = request.website.sale_product_domain()
        if search:
            for srch in search.split(" "):
                domain += [
                    '|', '|', '|', ('name', 'ilike', srch), ('description', 'ilike', srch),
                    ('description_sale', 'ilike', srch), ('product_variant_ids.default_code', 'ilike', srch)]

        if category:
            domain += [('public_categ_ids', 'child_of', int(category))]

        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domain += [('attribute_line_ids.value_ids', 'in', ids)]
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domain += [('attribute_line_ids.value_ids', 'in', ids)]

        return domain

    @http.route([
        '''/shop''',
        '''/shop/line/<model("ws.product.line"):line>''',
        '''/shop/page/<int:page>''',
        '''/shop/category/<model("product.public.category"):category>''',
        '''/shop/category/<model("product.public.category"):category>/page/<int:page>'''
    ], type='http', auth="public", website=True, sitemap=sitemap_shop)
    def shop(self, page=0, category=None, search='', ppg=False, line=None, **post):
        add_qty = int(post.get('add_qty', 1))
        Category = request.env['product.public.category']
        if category:
            category = Category.search([('id', '=', int(category))], limit=1)
            if not category or not category.can_access_from_current_website():
                raise NotFound()
        else:
            category = Category

        # catch line
        Line = request.env['ws.product.line']
        if line:
            line = Line.sudo().search([('id', '=', int(line))])
            if not line:
                raise NotFound()
        _log.info("LINEA:::  %s " % line)

        if ppg:
            try:
                ppg = int(ppg)
                post['ppg'] = ppg
            except ValueError:
                ppg = False
        if not ppg:
            ppg = request.env['website'].get_current_website().shop_ppg or 20

        ppr = request.env['website'].get_current_website().shop_ppr or 4

        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
        attributes_ids = {v[0] for v in attrib_values}
        attrib_set = {v[1] for v in attrib_values}

        domain = self._get_search_domain(search, category, attrib_values)
        _log.info("DOMINIO ::: %s " % domain)
        if line:
            line_categs = line.product_catg_public_id.ids
            domain.append(('public_categ_ids', 'child_of', line_categs))

        _log.info("DOMINIO 2 ::::: %s " % domain)

        keep = QueryURL('/shop', category=category and int(category), search=search, attrib=attrib_list,
                        order=post.get('order'))

        pricelist_context, pricelist = self._get_pricelist_context()

        request.context = dict(request.context, pricelist=pricelist.id, partner=request.env.user.partner_id)

        url = "/shop"
        if search:
            post["search"] = search
        if attrib_list:
            post['attrib'] = attrib_list

        Product = request.env['product.template'].with_context(bin_size=True)

        search_product = Product.search(domain, order=self._get_search_order(post))
        _log.info(" PRODUCTOS ENCONTRADOS :::  %s " % len(search_product))
        website_domain = request.website.website_domain()
        categs_domain = [('parent_id', '=', False)] + website_domain
        if search:
            search_categories = Category.search(
                [('product_tmpl_ids', 'in', search_product.ids)] + website_domain).parents_and_self
            categs_domain.append(('id', 'in', search_categories.ids))
        else:
            search_categories = Category
        categs = Category.search(categs_domain)

        if category:
            url = "/shop/category/%s" % slug(category)

        product_count = len(search_product)
        pager = request.website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
        offset = pager['offset']
        products = search_product[offset: offset + ppg]

        ProductAttribute = request.env['product.attribute']
        if products:
            # get all products without limit
            attributes = ProductAttribute.search([('product_tmpl_ids', 'in', search_product.ids)])
        else:
            attributes = ProductAttribute.browse(attributes_ids)

        layout_mode = request.session.get('website_sale_shop_layout_mode')
        if not layout_mode:
            if request.website.viewref('website_sale.products_list_view').active:
                layout_mode = 'list'
            else:
                layout_mode = 'grid'

        values = {
            'search': search,
            'category': category,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'pricelist': pricelist,
            'add_qty': add_qty,
            'products': products,
            'search_count': product_count,  # common for all searchbox
            'bins': TableCompute().process(products, ppg, ppr),
            'ppg': ppg,
            'ppr': ppr,
            'categories': categs,
            'attributes': attributes,
            'keep': keep,
            'search_categories_ids': search_categories.ids,
            'layout_mode': layout_mode,

        }
        if category:
            values['main_object'] = category
        return request.render("website_sale.products", values)


    # @http.route([
    #     '''/shop''',
    #     '''/shop/page/<int:page>''',
    #     '''/shop/category/<model("product.public.category"):category>''',
    #     '''/shop/category/<model("product.public.category"):categorys>/page/<int:page>''',
    #     '''/shop/line/<string:line_name>''',
    # ], type='http', auth="public", website=True)
    # def shop(self, page=0, category=None, search='', ppg=False, line_name=None, **post):
    #     line_name = line_name.upper() if line_name is not None else None
    #     add_qty = int(post.get('add_qty', 1))
    #     _log.info("La category::: %s " % category)
    #     Category = request.env['product.public.category']
    #     if category:
    #         category = Category.search([('id', '=', int(category))], limit=1)
    #         if not category or not category.can_access_from_current_website():
    #             raise NotFound()
    #     else:
    #         category = Category
    #     line = request.env['ws.product.line'].sudo().search([('name', 'like', line_name)])[:1]
    #     line_categories = line.mapped('product_catg_public_id')
    #     if ppg:
    #         try:
    #             ppg = int(ppg)
    #             post['ppg'] = ppg
    #         except ValueError:
    #             ppg = False
    #     if not ppg:
    #         ppg = request.env['website'].get_current_website().shop_ppg or 20
    #
    #     ppr = request.env['website'].get_current_website().shop_ppr or 4
    #
    #     attrib_list = request.httprequest.args.getlist('attrib')
    #     attrib_values = [[int(x) for x in v.split("-")] for v in attrib_list if v]
    #     attributes_ids = {v[0] for v in attrib_values}
    #     attrib_set = {v[1] for v in attrib_values}
    #
    #     domain = self._get_search_domain(search, category, attrib_values)
    #
    #     keep = QueryURL('/shop', category=category and int(category), search=search, attrib=attrib_list,
    #                     order=post.get('order'))
    #
    #     pricelist_context, pricelist = self._get_pricelist_context()
    #
    #     request.context = dict(request.context, pricelist=pricelist.id, partner=request.env.user.partner_id)
    #
    #     url = "/shop"
    #     if search:
    #         post["search"] = search
    #     if attrib_list:
    #         post['attrib'] = attrib_list
    #
    #     Product = request.env['product.template'].with_context(bin_size=True)
    #
    #     search_product = Product.search(domain)
    #
    #     # Filtering all products that have the selected categories from line.
    #     products_ok = []
    #     for p in search_product:
    #         product_ok = False
    #         for cid in p.public_categ_ids.ids:
    #             if cid in line_categories.ids:
    #                 product_ok = True
    #         if product_ok:
    #             products_ok.append(p.id)
    #
    #     search_product_wlines = search_product.filtered(lambda pr: pr.id in products_ok)
    #
    #
    #     website_domain = request.website.website_domain()
    #     categs_domain = [('parent_id', '=', False)] + website_domain
    #     if line_name != None :
    #         categs_domain += [('id', 'in', line_categories.ids)]
    #     if search:
    #         search_categories = Category.search(
    #             [('product_tmpl_ids', 'in', search_product.ids)] + website_domain).parents_and_self
    #         categs_domain.append(('id', 'in', search_categories.ids))
    #     else:
    #         search_categories = Category
    #     categs = Category.search(categs_domain)
    #
    #     if category:
    #         url = "/shop/category/%s" % slug(category)
    #
    #     product_count = len(search_product)
    #     pager = request.website.pager(url=url, total=product_count, page=page, step=ppg, scope=7, url_args=post)
    #     products = Product.search(domain, limit=ppg, offset=pager['offset'], order=self._get_search_order(post))
    #     print(products)
    #
    #     ProductAttribute = request.env['product.attribute']
    #     if products:
    #         # get all products without limit
    #         attributes = ProductAttribute.search([('product_tmpl_ids', 'in', search_product.ids)])
    #     else:
    #         attributes = ProductAttribute.browse(attributes_ids)
    #
    #     layout_mode = request.session.get('website_sale_shop_layout_mode')
    #     if not layout_mode:
    #         if request.website.viewref('website_sale.products_list_view').active:
    #             layout_mode = 'list'
    #         else:
    #             layout_mode = 'grid'
    #     if line_name is not None:
    #         pager_lines = request.website.pager(url=url, total=len(search_product_wlines), page=page, step=ppg, scope=7,
    #                                             url_args=post)
    #         _log.info("Entra el modificado.. ")
    #         values = {
    #             'search': search,
    #             'category': category,
    #             'line_name': line_name,
    #             'attrib_values': attrib_values,
    #             'attrib_set': attrib_set,
    #             'pager': pager_lines,
    #             'pricelist': pricelist,
    #             'add_qty': add_qty,
    #             'products': search_product_wlines,
    #             'search_count': len(search_product_wlines),  # common for all searchbox
    #             'bins': TableCompute().process(search_product_wlines, ppg, ppr),
    #             'ppg': ppg,
    #             'ppr': ppr,
    #             'categories': categs,
    #             'attributes': attributes,
    #             'keep': keep,
    #             'search_categories_ids': search_categories.ids,
    #             'layout_mode': layout_mode,
    #         }
    #         return request.render("website_sale.products", values)
    #     else:
    #         _log.info("Entra  el original :: %s " % add_qty)
    #         values = {
    #             'search': search,
    #             'category': category,
    #             'attrib_values': attrib_values,
    #             'attrib_set': attrib_set,
    #             'pager': pager,
    #             'pricelist': pricelist,
    #             'add_qty': add_qty,
    #             'products': products,
    #             'search_count': product_count,  # common for all searchbox
    #             'bins': TableCompute().process(products, ppg, ppr),
    #             'ppg': ppg,
    #             'ppr': ppr,
    #             'categories': categs,
    #             'attributes': attributes,
    #             'keep': keep,
    #             'search_categories_ids': search_categories.ids,
    #             'layout_mode': layout_mode,
    #         }
    #         if category:
    #             values['main_object'] = category
    #         return request.render("website_sale.products", values)
