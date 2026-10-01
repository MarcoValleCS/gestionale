from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.ProductListView.as_view(), name="product_list"),
    path("nuovo/", views.ProductCreateView.as_view(), name="product_create"),
    path("importa/", views.product_import, name="product_import"),
    path("importa/modello/", views.product_import_template, name="product_import_template"),
    path("categorie/", views.CategoryListView.as_view(), name="category_list"),
    path("categorie/nuova/", views.CategoryCreateView.as_view(), name="category_create"),
    path("categorie/<int:pk>/", views.CategoryUpdateView.as_view(), name="category_update"),
    path("<int:pk>/", views.ProductDetailView.as_view(), name="product_detail"),
    path("<int:pk>/modifica/", views.ProductUpdateView.as_view(), name="product_update"),
    path("<int:pk>/default/", views.product_defaults, name="product_defaults"),
    path("<int:pk>/varianti/", views.product_variants_create, name="product_variants_create"),
    path("<int:pk>/componenti/aggiungi/", views.product_component_add, name="product_component_add"),
    path("<int:pk>/componenti/rimuovi/", views.product_component_remove, name="product_component_remove"),
    path("crea-rapido/", views.product_quick_create, name="quick_create"),
    path("cerca/", views.product_search, name="search"),
]
