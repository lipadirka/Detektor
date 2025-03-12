
'''
Функция детекции рамок
'''
# Использование библиотек
import itertools # перебор элементов по одному
import logging
import math
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

def layout_sheet(layout):
    # Форматы листов
    base_formats = {
        "A0": (841, 1189), "A1": (594, 841), "A2": (420, 594),
        "A3": (297, 420), "A4": (210, 297), "A5": (148, 210)
        
    }

    def toleran(size):
        # Погрешности рамок
        return max(5.0, size * 0.015)

    # Ограничение в размерах линий
    MIN_SIZE = 200  
    # Найденные листы
    found_sheets = []
    # Обработанные объекты
    processed_entities = set()
    # Обнаруженные прямоугольники (возможные рамки)
    detected_rectangles = set()

    # Функция обнаружения образования рамок
    def is_perpendicular(v1, v2):
        return abs(v1[0] * v2[0] + v1[1] * v2[1]) < 1e-3

    def is_rectangle(points):
        if len(points) != 4:
            return False

        v1 = (points[1][0] - points[0][0], points[1][1] - points[0][1])
        v2 = (points[2][0] - points[1][0], points[2][1] - points[1][1])
        v3 = (points[3][0] - points[2][0], points[3][1] - points[2][1])
        v4 = (points[0][0] - points[3][0], points[0][1] - points[3][1])

        return all([is_perpendicular(v1, v2), is_perpendicular(v2, v3),
                    is_perpendicular(v3, v4), is_perpendicular(v4, v1)])

    
    def extract_block(block, processed):
        extracted = set()
        for entity in block:
            if entity in processed:
                continue
            processed.add(entity)

            if entity.dxftype() == "INSERT":
                print(f"Обнаружен вложенный блок: {entity.dxf.name}, ({layout.name})")
                try:
                    sub_block = block.doc.blocks.get(entity.dxf.name)
                    extracted |= extract_block(sub_block, processed)
                except Exception as e:
                    logging.error(f"Ошибка при обработке блока {entity.dxf.name}, ({layout.name}): {e}")
            else:
                extracted.add(entity)
        return extracted

    # Поиск замкнутых контуров
    def closed_rectangles(lines):
        rects = []
        points_dict = {}

        for p1, p2 in lines:
            points_dict.setdefault(p1, []).append(p2)
            points_dict.setdefault(p2, []).append(p1)

        for quad in itertools.combinations(points_dict.keys(), 4):
            sorted_quad = tuple(sorted(quad))
            if sorted_quad not in detected_rectangles and len(set(sorted_quad)) == 4 and is_rectangle(sorted_quad):
                detected_rectangles.add(sorted_quad)
                rects.append(sorted_quad)
                logging.debug(f"Найден прямоугольник: {sorted_quad}, ({layout.name})")

        return rects


    # Извлечение рамок
    def extract_rectangles(entities):
        rects = []
        lines = {}
        logging.info("Поиск рамок...")

        for entity in entities:
            if entity in processed_entities:
                continue
            processed_entities.add(entity)

            if entity.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
                points = tuple(entity.vertices())
                if entity.is_closed and len(points) == 4 and is_rectangle(points):
                    width = abs(points[0][0] - points[2][0])
                    height = abs(points[0][1] - points[2][1])

                    if width >= MIN_SIZE and height >= MIN_SIZE:
                        round_points = tuple(sorted((round(p[0], 2), round(p[1], 2)) for p in points))
                        if round_points not in detected_rectangles:
                            detected_rectangles.add(round_points)
                            rects.append(points)
                            logging.debug(f"Найден прямоугольник (полилиния): {round_points}, ({layout.name})")
                else:
                    logging.debug(f"Пропущена полилиния: не замкнута ({layout.name})")

            elif entity.dxftype() == "LINE":
                p1 = (entity.dxf.start.x, entity.dxf.start.y)
                p2 = (entity.dxf.end.x, entity.dxf.end.y)

                if math.dist(p1, p2) < MIN_SIZE:
                    continue
                lines[frozenset([p1, p2])] = (p1, p2)

        if len(lines) >= 4:         
            rects.extend(closed_rectangles(list(lines.values())))

        return rects

    # Проверка размеров прямоугольников
    def check_size(rect):
        if len(rect) != 4:
            return

        xs, ys = zip(*rect)
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        width, height = abs(max_x - min_x), abs(max_y - min_y)

        if width < MIN_SIZE or height < MIN_SIZE:
            return

        for fmt, (fw, fh) in base_formats.items():
            tol_w, tol_h = toleran(fw), toleran(fh)
            if (abs(width - fw) <= tol_w and abs(height - fh) <= tol_h) or \
               (abs(width - fh) <= tol_h and abs(height - fw) <= tol_w):
                found_sheets.append((fmt, width, height, layout.name))
                logging.info(f"Обнаружен лист {fmt} ({round(width, 2)}x{round(height, 2)})")
                break

    entities = set(layout)
    for entity in layout.query("INSERT"):
        try:
            block = layout.doc.blocks.get(entity.dxf.name)
            entities |= extract_block(block, processed_entities)
        except Exception as e:
            logging.error(f"Ошибка обработки блока {layout.name}, {entity.dxf.name}: {e}")
    
            # Определение границ блока
            min_x, min_y, max_x, max_y = float("inf"), float("inf"), float("-inf"), float("-inf")
            for sub_entity in block:
                if sub_entity.dxftype() in ["LINE", "LWPOLYLINE", "POLYLINE"]:
                    for p in sub_entity.get_points():
                        min_x, min_y = min(min_x, p[0]), min(min_y, p[1])
                        max_x, max_y = max(max_x, p[0]), max(max_y, p[1])

            width, height = max_x - min_x, max_y - min_y

            if width < MIN_SIZE or height < MIN_SIZE:
                continue  

            for sub_entity in block:
                if sub_entity not in processed_entities:
                    entities.add(sub_entity)

        except Exception as e:
            logging.error(f"Ошибка обработки блока во вкладке '{layout.name}': {e}")
            pass

    # Поиск элементов среди прямоугольн.
    rectangles = extract_rectangles(entities)
    
    for rect in rectangles:
        check_size(rect)
    if not rectangles:
            logging.warning(f"Вкладка '{layout.name}': рамки не найдены.")
            
    # Удаление дубликатов листов
    found_sheets = list(set(found_sheets))

    # Фильтрация листов
    filtered_sheets = []
    for sheet in found_sheets:
        fmt, w, h, bbox = sheet
        if not any((w2 > w and h2 > h) for _, w2, h2, _ in found_sheets if (w, h) != (w2, h2)):
            filtered_sheets.append(sheet)

   
    round_sheets = [(fmt, round(w, 2), round(h, 2), bbox) for fmt, w, h, bbox in filtered_sheets]
    logging.info(f"Обнаружены листы: {round_sheets}")

    return filtered_sheets if filtered_sheets else None
