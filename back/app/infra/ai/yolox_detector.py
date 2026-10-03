from __future__ import annotations

from pathlib import Path
from threading import Lock

import cv2
import numpy as np

from app.domain.detection import Detection
from app.domain.enums import PetSpecies


CAT_CLASS_INDEX = 15
DOG_CLASS_INDEX = 16
PET_CLASS_INDICES = {
    PetSpecies.CAT: CAT_CLASS_INDEX,
    PetSpecies.DOG: DOG_CLASS_INDEX,
}


class YoloXDetector:
    def __init__(self, model_path: Path, confidence: float = 0.35, nms: float = 0.45) -> None:
        self.model_path = model_path
        self.confidence = confidence
        self.nms = nms
        self.input_size = 416
        self._network = cv2.dnn.readNetFromONNX(str(model_path))
        self._lock = Lock()

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        ratio = min(self.input_size / height, self.input_size / width)
        resized_width = int(width * ratio)
        resized_height = int(height * ratio)
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
        padded = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        padded[:resized_height, :resized_width] = resized
        blob = padded.transpose(2, 0, 1).astype(np.float32)[None]
        with self._lock:
            self._network.setInput(blob)
            output = self._network.forward()
        predictions = self._decode(output)[0]
        class_scores = predictions[:, 5:]
        pet_scores = np.stack([class_scores[:, index] * predictions[:, 4] for index in PET_CLASS_INDICES.values()], axis=1)
        best_classes = np.argmax(pet_scores, axis=1)
        scores = pet_scores[np.arange(len(predictions)), best_classes]
        species = np.array(list(PET_CLASS_INDICES), dtype=object)[best_classes]
        selected = scores >= self.confidence
        predictions = predictions[selected]
        scores = scores[selected]
        species = species[selected]
        if not len(predictions):
            return []
        centers = predictions[:, :2]
        sizes = predictions[:, 2:4]
        top_left = centers - sizes / 2
        boxes = np.concatenate((top_left, sizes), axis=1) / ratio
        detections: list[Detection] = []
        for pet_species in PET_CLASS_INDICES:
            class_indices = np.flatnonzero(species == pet_species)
            if not len(class_indices):
                continue
            selected_boxes = boxes[class_indices]
            selected_scores = scores[class_indices]
            indices = cv2.dnn.NMSBoxes(selected_boxes.tolist(), selected_scores.tolist(), self.confidence, self.nms)
            for raw_index in indices:
                index = int(np.asarray(raw_index).reshape(-1)[0])
                x, y, box_width, box_height = selected_boxes[index]
                detections.append(Detection(
                    x1=max(0.0, min(1.0, float(x / width))),
                    y1=max(0.0, min(1.0, float(y / height))),
                    x2=max(0.0, min(1.0, float((x + box_width) / width))),
                    y2=max(0.0, min(1.0, float((y + box_height) / height))),
                    confidence=float(selected_scores[index]),
                    species=pet_species,
                ))
        return detections

    def _decode(self, output: np.ndarray) -> np.ndarray:
        predictions = output.reshape(1, -1, output.shape[-1]).copy()
        grids: list[np.ndarray] = []
        strides: list[np.ndarray] = []
        for stride in (8, 16, 32):
            size = self.input_size // stride
            y_grid, x_grid = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
            grid = np.stack((x_grid, y_grid), axis=2).reshape(1, -1, 2)
            grids.append(grid)
            strides.append(np.full((*grid.shape[:2], 1), stride))
        grid = np.concatenate(grids, axis=1)
        stride = np.concatenate(strides, axis=1)
        predictions[..., :2] = (predictions[..., :2] + grid) * stride
        predictions[..., 2:4] = np.exp(predictions[..., 2:4]) * stride
        return predictions
