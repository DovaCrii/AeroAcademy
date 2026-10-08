from django.contrib import admin

from .models import MilestoneCheck, PathGoal, QuizAnswer


@admin.register(MilestoneCheck)
class MilestoneCheckAdmin(admin.ModelAdmin):
    list_display = ("person", "milestone", "checked_at")
    list_filter = ("milestone__path",)
    raw_id_fields = ("person", "milestone")


@admin.register(QuizAnswer)
class QuizAnswerAdmin(admin.ModelAdmin):
    list_display = ("person", "question", "selected_index", "answered_at")
    list_filter = ("question__path",)
    raw_id_fields = ("person", "question")


@admin.register(PathGoal)
class PathGoalAdmin(admin.ModelAdmin):
    list_display = ("person", "path", "certification_goal")
    list_filter = ("path",)
    raw_id_fields = ("person",)
