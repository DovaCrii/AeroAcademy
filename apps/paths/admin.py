from django.contrib import admin

from .models import (
    ExternalCourse,
    LearningPath,
    Level,
    LevelResource,
    Milestone,
    PathExtra,
    QuizQuestion,
    SharedItem,
)


class LevelInline(admin.TabularInline):
    model = Level
    extra = 0
    fields = ("code", "order", "short", "title", "completion_rule")
    show_change_link = True


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ("title", "vendor", "kind", "world", "is_published")
    list_filter = ("vendor", "kind", "world", "is_published")
    filter_horizontal = ("products", "disciplines")
    inlines = [LevelInline]


class LevelResourceInline(admin.TabularInline):
    model = LevelResource
    extra = 0


@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ("__str__", "title", "order")
    list_filter = ("path",)
    inlines = [LevelResourceInline]


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ("key", "path", "level", "retired")
    list_filter = ("path", "retired")
    search_fields = ("key", "text")


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("key", "path", "level", "retired")
    list_filter = ("path", "retired")


@admin.register(ExternalCourse)
class ExternalCourseAdmin(admin.ModelAdmin):
    list_display = ("key", "path", "level", "reward", "is_required", "retired")
    list_filter = ("path", "reward", "retired")
    filter_horizontal = ("disciplines",)


@admin.register(PathExtra)
class PathExtraAdmin(admin.ModelAdmin):
    list_display = ("path", "kind", "order")
    list_filter = ("path", "kind")


@admin.register(SharedItem)
class SharedItemAdmin(admin.ModelAdmin):
    list_display = ("key", "path", "group_title")
    list_filter = ("path",)
