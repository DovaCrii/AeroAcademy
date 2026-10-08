from django.contrib import admin

from .models import Discipline, Platform, Product, Resource, Skill, Vendor


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "default_world", "order")


class ProductInline(admin.TabularInline):
    model = Product
    extra = 0
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    inlines = [ProductInline]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "vendor", "slug")
    list_filter = ("vendor",)
    filter_horizontal = ("disciplines",)


@admin.register(Platform)
class PlatformAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "vendor")
    list_filter = ("kind", "vendor")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "category", "attribute")
    list_filter = ("attribute", "category")
    search_fields = ("name", "slug")


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "platform", "kind", "is_free", "grants_completion_certificate")
    list_filter = ("platform", "kind", "is_free", "grants_completion_certificate", "verify_url")
    search_fields = ("title", "description")
    filter_horizontal = ("products", "disciplines", "skills")
