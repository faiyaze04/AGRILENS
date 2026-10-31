import os
import tensorflow as tf
from tensorflow.keras import layers

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, "dataset", "PlantVillage")
if not os.path.exists(DATA_FOLDER):
    DATA_FOLDER = r"G:\My Drive\EXPISCOR 2026\PlantVillage\PlantVillage"
IMAGE_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 20

def train():
    train_data = tf.keras.utils.image_dataset_from_directory(
        DATA_FOLDER,
        validation_split=0.2,
        subset="training",
        seed=123,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
    )

    validation_data = tf.keras.utils.image_dataset_from_directory(
        DATA_FOLDER,
        validation_split=0.2,
        subset="validation",
        seed=123,
        image_size=IMAGE_SIZE,
        batch_size=BATCH_SIZE,
    )

    init_model_path = os.path.join(BASE_DIR, "agri_lens_plant_disease_finetuned.keras")
    if not os.path.exists(init_model_path):
        init_model_path = os.path.join(BASE_DIR, "agri_lens_plant_disease.keras")
    model = tf.keras.models.load_model(init_model_path)

    base_model = next(
        layer for layer in model.layers
        if isinstance(layer, tf.keras.Model) and "mobilenet" in layer.name.lower()
    )

    base_model.trainable = True

    for layer in base_model.layers[:-30]:
        layer.trainable = False

    for layer in base_model.layers:
        if isinstance(layer, layers.BatchNormalization):
            layer.trainable = False

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.00001),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    out_model_path = os.path.join(BASE_DIR, "agri_lens_plant_disease_20epoch.keras")
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            mode="max",
            patience=2,
            restore_best_weights=True,
        ),
        tf.keras.callbacks.ModelCheckpoint(
            out_model_path,
            monitor="val_accuracy",
            mode="max",
            save_best_only=True,
        ),
    ]

    model.fit(
        train_data,
        validation_data=validation_data,
        epochs=EPOCHS,
        callbacks=callbacks,
    )

    print(f"Finished! Model saved as {out_model_path}")

if __name__ == "__main__":
    train()