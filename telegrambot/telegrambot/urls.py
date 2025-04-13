from django.contrib import admin
from django.urls import path, include  # ✅ include is needed

urlpatterns = [
    path('admin/', admin.site.urls),
    path('bot/', include('bot.urls')),  # ✅ Add this line to include your bot app URLs
]

