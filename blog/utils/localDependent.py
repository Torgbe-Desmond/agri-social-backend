import tensorflow as tf
import numpy as np
from PIL import Image
import io

async def predict_image_class(file_bytes:bytes , model: tf.keras.Model):
    try:
        image = Image.open(io.BytesIO(file_bytes)).resize((256, 256))
        input_arr = tf.keras.preprocessing.image.img_to_array(image)
        input_arr = np.expand_dims(input_arr, axis=0)
        prediction = model.predict(input_arr)
        confidence = float(np.max(prediction))  
        result_index = np.argmax(prediction)
        return result_index, confidence
    except Exception as e:
        print(f"Prediction error: {e}")
        raise