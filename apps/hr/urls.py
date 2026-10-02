from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    # Dipendenti
    path("dipendenti/", views.EmployeeListView.as_view(), name="employee_list"),
    path("dipendenti/nuovo/", views.EmployeeCreateView.as_view(), name="employee_create"),
    path("dipendenti/<int:pk>/", views.EmployeeDetailView.as_view(), name="employee_detail"),
    path("dipendenti/<int:pk>/modifica/", views.EmployeeUpdateView.as_view(), name="employee_update"),
    path("dipendenti/<int:pk>/elimina/", views.employee_delete, name="employee_delete"),
    # Ore lavorate
    path("ore/", views.TimeEntryListView.as_view(), name="timeentry_list"),
    path("ore/nuova/", views.TimeEntryCreateView.as_view(), name="timeentry_create"),
    path("ore/rapida/", views.timeentry_bulk, name="timeentry_bulk"),
    path("ore/standard/", views.timeentry_standard, name="timeentry_standard"),
    path("ore/<int:pk>/modifica/", views.TimeEntryUpdateView.as_view(), name="timeentry_update"),
    path("ore/<int:pk>/elimina/", views.timeentry_delete, name="timeentry_delete"),
    # Ferie e permessi
    path("assenze/", views.LeaveListView.as_view(), name="leave_list"),
    path("assenze/nuova/", views.LeaveCreateView.as_view(), name="leave_create"),
    path("assenze/<int:pk>/modifica/", views.LeaveUpdateView.as_view(), name="leave_update"),
    path("assenze/<int:pk>/approva/", views.leave_approve, name="leave_approve"),
    path("assenze/<int:pk>/rifiuta/", views.leave_reject, name="leave_reject"),
    path("assenze/<int:pk>/elimina/", views.leave_delete, name="leave_delete"),
    # Collaboratori (gestione dall'ufficio)
    path("collaboratori/", views.CollaboratorListView.as_view(), name="collaborator_list"),
    path("collaboratori/nuovo/", views.CollaboratorCreateView.as_view(), name="collaborator_create"),
    path("collaboratori/<int:pk>/modifica/", views.CollaboratorUpdateView.as_view(), name="collaborator_update"),
    path("collaboratori/<int:pk>/elimina/", views.collaborator_delete, name="collaborator_delete"),
    path("collaboratori/ore/", views.CollaboratorTimeListView.as_view(), name="collaborator_time_list"),
    path("collaboratori/ore/<int:pk>/elimina/", views.collaborator_time_delete, name="collaborator_time_delete"),
    path("presenze/", views.timesheet, name="timesheet"),
    # Collaboratori esterni: area riservata a chi rendiconta le ore
    path("mio-lavoro/", views.collaborator_area, name="collaborator_area"),
    path("mio-lavoro/nuova/", views.collaborator_entry_create, name="collaborator_entry_create"),
    path("mio-lavoro/<int:pk>/modifica/", views.collaborator_entry_update, name="collaborator_entry_update"),
    path("mio-lavoro/<int:pk>/elimina/", views.collaborator_entry_delete, name="collaborator_entry_delete"),
    path("mio-lavoro/foto/", views.collaborator_photos, name="collaborator_photos"),
    path("mio-lavoro/foto/<int:pk>/elimina/", views.collaborator_photo_delete, name="collaborator_photo_delete"),
]
