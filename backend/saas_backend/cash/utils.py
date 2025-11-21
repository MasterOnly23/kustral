import os
import shutil
from django.conf import settings

def move_photo_to_deleted_folder(photo_instance):
    old_path = photo_instance.image.path

    filename = os.path.basename(old_path)
    new_folder = os.path.join(settings.MEDIA_ROOT, "cash_photos_deleted")
    os.makedirs(new_folder, exist_ok=True)

    new_path = os.path.join(new_folder, filename)

    # Mover el archivo
    shutil.move(old_path, new_path)

    # Actualizar la ruta en la BD
    photo_instance.image.name = f"cash_photos_deleted/{filename}"
    photo_instance.save(update_fields=["image"])
