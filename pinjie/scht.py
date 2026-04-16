import os
import numpy as np
import cv2
from collections import Counter
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import json

# 解决中文显示问题
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class InteractiveStitchingGUI:
    def __init__(self, images, stitching_results, classification):
        self.images = images
        self.stitching_results = stitching_results
        self.classification = classification
        self.current_arrangement = self.stitching_results.copy()
        self.scale_factor = 0.5  # 缩放因子

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("图像拼接结果编辑器")
        self.root.geometry("1200x800")

        # 拖拽状态
        self.dragging = False
        self.drag_data = None

        self.setup_ui()
        self.update_display()

    def setup_ui(self):
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制面板
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        ttk.Button(control_frame, text="保存当前排列",
                   command=self.save_arrangement).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="重置为原始结果",
                   command=self.reset_arrangement).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="导出拼接图像",
                   command=self.export_stitched_images).pack(side=tk.LEFT, padx=(0, 10))

        # 缩放控制
        ttk.Label(control_frame, text="缩放:").pack(side=tk.LEFT, padx=(20, 5))
        self.scale_var = tk.DoubleVar(value=self.scale_factor)
        scale_spinbox = ttk.Spinbox(control_frame, from_=0.1, to=2.0, increment=0.1,
                                    textvariable=self.scale_var, width=10,
                                    command=self.on_scale_change)
        scale_spinbox.pack(side=tk.LEFT, padx=(0, 10))

        # 滚动区域
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg='white')
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)

        # 布局
        self.canvas.grid(row=0, column=0, sticky='nsew')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')

        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)

        # 绑定事件
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_scale_change(self):
        self.scale_factor = self.scale_var.get()
        self.update_display()

    def resize_image(self, img, scale):
        """调整图像大小"""
        h, w = img.shape[:2]
        new_h, new_w = int(h * scale), int(w * scale)
        return cv2.resize(img, (new_w, new_h))

    def update_display(self):
        """更新显示"""
        self.canvas.delete("all")
        self.image_positions = {}

        y_offset = 20
        max_width = 0

        for cluster_id, indices in self.current_arrangement.items():
            if len(indices) == 0:
                continue

            # 绘制聚类标签
            cluster_text = f"Cluster {cluster_id + 1} ({len(indices)} images)"
            self.canvas.create_text(20, y_offset, text=cluster_text, anchor="w",
                                    font=("Arial", 12, "bold"), fill="blue")
            y_offset += 30

            # 绘制该聚类的图像
            x_offset = 20
            row_height = 0

            for i, img_idx in enumerate(indices):
                # 调整图像大小
                img = self.resize_image(self.images[img_idx], self.scale_factor)

                # 转换为PIL图像
                if len(img.shape) == 3:
                    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                else:
                    pil_img = Image.fromarray(img)

                # 转换为tkinter格式
                photo = ImageTk.PhotoImage(pil_img)

                # 在画布上显示
                item_id = self.canvas.create_image(x_offset, y_offset, anchor="nw", image=photo)

                # 存储图像信息
                self.image_positions[item_id] = {
                    'cluster_id': cluster_id,
                    'img_idx': img_idx,
                    'position_in_cluster': i,
                    'photo': photo,  # 保持引用防止被垃圾回收
                    'x': x_offset,
                    'y': y_offset,
                    'width': pil_img.width,
                    'height': pil_img.height
                }

                # 添加边框和索引标签
                self.canvas.create_rectangle(x_offset - 2, y_offset - 2,
                                             x_offset + pil_img.width + 2, y_offset + pil_img.height + 2,
                                             outline="black", width=1)
                self.canvas.create_text(x_offset + 5, y_offset + 5, text=str(img_idx),
                                        anchor="nw", font=("Arial", 8), fill="red")

                x_offset += pil_img.width + 10
                row_height = max(row_height, pil_img.height)
                max_width = max(max_width, x_offset)

            y_offset += row_height + 30

        # 更新画布滚动区域
        self.canvas.configure(scrollregion=(0, 0, max_width + 20, y_offset + 20))

    def on_click(self, event):
        """鼠标点击事件"""
        # 转换画布坐标
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        # 查找点击的图像
        clicked_item = self.canvas.find_closest(canvas_x, canvas_y)[0]

        if clicked_item in self.image_positions:
            self.dragging = True
            self.drag_data = {
                'item_id': clicked_item,
                'start_x': canvas_x,
                'start_y': canvas_y,
                'original_cluster': self.image_positions[clicked_item]['cluster_id'],
                'original_position': self.image_positions[clicked_item]['position_in_cluster']
            }

            # 高亮显示被拖拽的图像
            img_info = self.image_positions[clicked_item]
            self.canvas.create_rectangle(img_info['x'] - 3, img_info['y'] - 3,
                                         img_info['x'] + img_info['width'] + 3,
                                         img_info['y'] + img_info['height'] + 3,
                                         outline="red", width=3, tags="highlight")

    def on_drag(self, event):
        """拖拽事件"""
        if self.dragging and self.drag_data:
            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            dx = canvas_x - self.drag_data['start_x']
            dy = canvas_y - self.drag_data['start_y']

            # 移动图像
            self.canvas.move(self.drag_data['item_id'], dx, dy)
            self.canvas.move("highlight", dx, dy)

            self.drag_data['start_x'] = canvas_x
            self.drag_data['start_y'] = canvas_y

    def on_release(self, event):
        """释放鼠标事件"""
        if self.dragging and self.drag_data:
            self.canvas.delete("highlight")

            canvas_x = self.canvas.canvasx(event.x)
            canvas_y = self.canvas.canvasy(event.y)

            # 查找目标位置
            target_cluster, target_position = self.find_drop_target(canvas_x, canvas_y)

            if target_cluster is not None:
                # 执行移动操作
                self.move_image(self.drag_data['item_id'], target_cluster, target_position)
                self.update_display()
            else:
                # 如果没有有效目标，恢复原位置
                self.update_display()

            self.dragging = False
            self.drag_data = None

    def find_drop_target(self, x, y):
        """查找拖放目标位置"""
        # 查找最近的聚类行
        min_distance = float('inf')
        target_cluster = None
        target_position = None

        for cluster_id, indices in self.current_arrangement.items():
            if len(indices) == 0:
                continue

            # 计算到该聚类中心的距离
            cluster_y = self.get_cluster_y_position(cluster_id)
            distance = abs(y - cluster_y)

            if distance < min_distance and distance < 100:  # 100像素的容差
                min_distance = distance
                target_cluster = cluster_id

                # 在该聚类中查找插入位置
                target_position = self.find_insert_position(cluster_id, x)

        return target_cluster, target_position

    def get_cluster_y_position(self, cluster_id):
        """获取聚类的Y坐标位置"""
        y_offset = 50  # 初始偏移
        for cid in range(cluster_id):
            if len(self.current_arrangement[cid]) > 0:
                y_offset += int(self.images[0].shape[0] * self.scale_factor) + 60
        return y_offset

    def find_insert_position(self, cluster_id, x):
        """在聚类中查找插入位置"""
        indices = self.current_arrangement[cluster_id]
        if len(indices) == 0:
            return 0

        # 计算每个图像的X位置
        x_offset = 20
        img_width = int(self.images[0].shape[1] * self.scale_factor)

        for i, img_idx in enumerate(indices):
            if x < x_offset + img_width // 2:
                return i
            x_offset += img_width + 10

        return len(indices)

    def move_image(self, item_id, target_cluster, target_position):
        """移动图像到新位置"""
        img_info = self.image_positions[item_id]
        img_idx = img_info['img_idx']
        source_cluster = img_info['cluster_id']
        source_position = img_info['position_in_cluster']

        # 从原位置移除
        self.current_arrangement[source_cluster].pop(source_position)

        # 插入到新位置
        if target_cluster not in self.current_arrangement:
            self.current_arrangement[target_cluster] = []

        if target_position >= len(self.current_arrangement[target_cluster]):
            self.current_arrangement[target_cluster].append(img_idx)
        else:
            self.current_arrangement[target_cluster].insert(target_position, img_idx)

        print(f"移动图像 {img_idx}: Cluster {source_cluster} -> Cluster {target_cluster}")

    def save_arrangement(self):
        """保存当前排列到文件"""
        try:
            filename = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                title="保存排列配置"
            )

            if filename:
                # 转换为可序列化格式
                save_data = {
                    'arrangement': {str(k): v for k, v in self.current_arrangement.items()},
                    'timestamp': str(np.datetime64('now'))
                }

                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(save_data, f, ensure_ascii=False, indent=2)

                messagebox.showinfo("成功", f"排列已保存到: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {str(e)}")

    def reset_arrangement(self):
        """重置为原始排列"""
        self.current_arrangement = self.stitching_results.copy()
        self.update_display()
        messagebox.showinfo("完成", "已重置为原始拼接结果")

    def export_stitched_images(self):
        """导出拼接后的图像"""
        try:
            save_dir = filedialog.askdirectory(title="选择保存目录")
            if not save_dir:
                return

            for cluster_id, indices in self.current_arrangement.items():
                if len(indices) <= 1:
                    continue

                # 水平拼接该聚类的图像
                cluster_images = [self.images[idx] for idx in indices]

                if len(cluster_images) > 0:
                    # 确保所有图像高度一致
                    max_height = max(img.shape[0] for img in cluster_images)
                    resized_images = []

                    for img in cluster_images:
                        if img.shape[0] < max_height:
                            # 垂直居中填充
                            pad_top = (max_height - img.shape[0]) // 2
                            pad_bottom = max_height - img.shape[0] - pad_top
                            img = np.pad(img, ((pad_top, pad_bottom), (0, 0)),
                                         mode='constant', constant_values=255)
                        resized_images.append(img)

                    # 水平拼接
                    stitched = np.hstack(resized_images)

                    # 保存
                    filename = f"cluster_{cluster_id + 1}_stitched.png"
                    filepath = os.path.join(save_dir, filename)
                    cv2.imwrite(filepath, stitched)

                    print(f"已保存: {filepath}")

            # 保存排列信息
            arrangement_file = os.path.join(save_dir, "arrangement_info.txt")
            with open(arrangement_file, 'w', encoding='utf-8') as f:
                f.write("最终拼接排列结果\n")
                f.write("=" * 50 + "\n\n")

                for cluster_id, indices in self.current_arrangement.items():
                    if len(indices) > 0:
                        f.write(f"Cluster {cluster_id + 1}: {indices}\n")

            messagebox.showinfo("完成", f"拼接图像已导出到: {save_dir}")

        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def run(self):
        """运行GUI"""
        self.root.mainloop()


def tabulate_cumsum(arr):
    unique_vals, counts = np.unique(arr, return_counts=True)
    return np.array([unique_vals, counts])


# ------------------------------
# 拼接算法模块
# ------------------------------
def extract_edges(img, width=1):
    """提取左右边缘特征"""
    left = img[:, :width].flatten().astype(np.float32)
    right = img[:, -width:].flatten().astype(np.float32)
    return left, right


def compute_cost_matrix(pieces):
    """计算碎片间匹配代价矩阵"""
    n = len(pieces)
    cost = np.full((n, n), np.inf)

    for i in range(n):
        for j in range(n):
            if i != j:
                # 计算右边缘i与左边缘j的欧氏距离
                cost[i, j] = np.sum((pieces[i]['right'] - pieces[j]['left']) ** 2)

    return cost


def find_optimal_order(cost_matrix, pieces):
    """动态规划求解最优排列"""
    n = cost_matrix.shape[0]
    if n == 0:
        return []
    if n == 1:
        return [0]

    INF = float('inf')

    # 初始化DP表
    dp = [[INF] * n for _ in range(1 << n)]
    prev = [[-1] * n for _ in range(1 << n)]

    # 寻找起始碎片（左边缘最接近白色）
    start = np.argmax([np.mean(p['left']) for p in pieces])
    dp[1 << start][start] = 0

    # 状态转移
    for mask in range(1 << n):
        for i in range(n):
            if not (mask & (1 << i)) or dp[mask][i] == INF:
                continue
            for j in range(n):
                if not (mask & (1 << j)) and cost_matrix[i, j] < INF:
                    new_mask = mask | (1 << j)
                    if dp[new_mask][j] > dp[mask][i] + cost_matrix[i, j]:
                        dp[new_mask][j] = dp[mask][i] + cost_matrix[i, j]
                        prev[new_mask][j] = i

    # 回溯路径
    mask = (1 << n) - 1
    end = np.argmin([dp[mask][i] for i in range(n)])

    order = []
    current = end
    while current != -1:
        order.append(current)
        next_mask = mask ^ (1 << current)
        current = prev[mask][current]
        mask = next_mask

    return order[::-1]


def stitch_cluster(img_list, cluster_indices):
    """对聚类中的图像进行拼接"""
    if len(cluster_indices) == 0:
        return []

    # 提取边缘特征
    pieces = []
    for idx in cluster_indices:
        img = img_list[idx]
        left, right = extract_edges(img)
        pieces.append({'left': left, 'right': right, 'original_idx': idx})

    # 计算匹配代价
    cost_matrix = compute_cost_matrix(pieces)

    # 动态规划求解
    local_order = find_optimal_order(cost_matrix, pieces)

    # 转换为原始图像索引
    global_order = [pieces[i]['original_idx'] for i in local_order]

    return global_order


def process_images():
    # 获取文件列表
    file_path = 'tu2'
    if not os.path.exists(file_path):
        print(f"路径 {file_path} 不存在，请检查路径")
        return

    files = [f for f in os.listdir(file_path) if f.endswith('.bmp')]
    files.sort()  # 确保文件顺序一致

    if not files:
        print("未找到BMP文件")
        return

    print(f"找到 {len(files)} 个BMP文件")

    # 读取图像
    img = []
    for i, filename in enumerate(files):
        f = os.path.join(file_path, filename)
        image = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        if image is not None:
            img.append(image)
        else:
            print(f"无法读取文件: {filename}")

    if not img:
        print("没有成功读取任何图像")
        return

    # 获取图像尺寸
    L, W = img[0].shape
    print(f"图像尺寸: {L} x {W}")

    # 提取左右边缘
    img_left = np.zeros((L, len(files)))
    img_right = np.zeros((L, len(files)))

    for i in range(len(files)):
        img_left[:, i] = img[i][:, 0]
        img_right[:, i] = img[i][:, -1]

    # 图像变换处理
    img_trans = np.zeros((L, len(files)))

    for i in range(len(files)):
        img_trans_temp = img[i].copy()
        img_trans_temp = 255 - img_trans_temp
        img_trans[:, i] = np.sum(img_trans_temp, axis=1)

    # 二值化处理
    img_trans[img_trans != 0] = 255
    img_trans = 255 - img_trans
    img_trans[img_trans != 0] = 1

    # 显示第一个处理后的图像
    plt.figure(figsize=(10, 6))
    plt.imshow(img_trans[:, 0].reshape(-1, 1), cmap='gray')
    plt.title('Processed First Image')
    plt.show()

    # 计算连续段长度
    num_0 = {}
    num_1 = {}

    for i in range(len(files)):
        a = img_trans[:, i].copy()

        if a[0] == 0:
            a = np.concatenate([[0], a])
            cumsum_a = np.cumsum(a)
            f_0 = tabulate_cumsum(cumsum_a)
            num_0[i] = f_0[1, :] - 1
            num_0[i] = num_0[i][num_0[i] != 0]

            cumsum_1_a = np.cumsum(1 - a)
            f_1 = tabulate_cumsum(cumsum_1_a)
            num_1[i] = f_1[1, :] - 1
            num_1[i] = num_1[i][num_1[i] != 0]
        else:
            cumsum_a = np.cumsum(a)
            f_0 = tabulate_cumsum(cumsum_a)
            num_0[i] = f_0[1, :] - 1
            num_0[i] = num_0[i][num_0[i] != 0]

            cumsum_1_a = np.cumsum(np.concatenate([[0], 1 - a]))
            f_1 = tabulate_cumsum(cumsum_1_a)
            num_1[i] = f_1[1, :] - 1
            num_1[i] = num_1[i][num_1[i] != 0]

    # 第一轮处理
    img_trans_1 = img_trans.copy()
    count11 = 0
    count12 = 0

    for i in range(len(files)):
        if len(num_1[i]) > 0:
            if num_1[i][0] >= 69:
                start_idx = int(max(0, num_1[i][0] - 28 - 40))
                end_idx = int(min(L, num_1[i][0] - 28 + 1))
                img_trans_1[start_idx:end_idx, i] = 0
                count11 += 1
            elif num_1[i][0] >= 28 and img_trans[0, i] == 1:
                end_idx = int(max(0, num_1[i][0] - 28))
                img_trans_1[0:end_idx, i] = 0
                count12 += 1

    print(f"第一轮处理: count11={count11}, count12={count12}")

    # 第二轮处理
    img_trans_2 = img_trans_1.copy()
    count21 = 0
    count22 = 0

    for i in range(len(files)):
        if len(num_1[i]) > 0 and len(num_0[i]) > 0:
            if num_1[i][0] >= 69 and img_trans[0, i] == 0:
                start_idx = int(num_0[i][0] + 28)
                end_idx = int(min(L, num_1[i][0] + 28 + 41))
                img_trans_2[start_idx:end_idx, i] = 0
                count21 += 1
            elif num_1[i][0] >= 69 and img_trans[0, i] == 1:
                start_idx = int(num_0[i][0] + num_1[i][0] + 29)
                end_idx = int(min(L, start_idx + 41))
                img_trans_2[start_idx:end_idx, i] = 0
                count22 += 1

    print(f"第二轮处理: count21={count21}, count22={count22}")

    # 第三轮处理
    img_trans_3 = img_trans_2.copy()
    count31 = 0
    count32 = 0
    count33 = 0
    count34 = 0

    for i in range(len(files)):
        if len(num_1[i]) >= 3:  # 超过一行白色一行黑色的最大情况认为其有缺失
            if num_1[i][2] >= 30:
                if len(num_0[i]) >= 2:
                    start_idx = int(num_0[i][0] + num_1[i][0] + num_0[i][1] + num_1[i][1] + 28)
                    img_trans_3[start_idx:, i] = 0
                    count31 += 1
        elif len(num_1[i]) == 2:
            if len(num_0[i]) >= 2:
                if num_1[i][1] >= 69 and img_trans[0, i] == 0:
                    start_idx = int(num_0[i][0] + num_1[i][0] + num_0[i][1] + 28)
                    end_idx = int(min(L, start_idx + 41))
                    img_trans_3[start_idx:end_idx, i] = 0
                    count32 += 1
                elif num_1[i][1] >= 69 and img_trans[0, i] == 1:
                    start_idx = int(num_0[i][0] + num_1[i][1] + num_1[i][0] + 29)
                    end_idx = int(min(L, start_idx + 41))
                    img_trans_3[start_idx:end_idx, i] = 0
                    count33 += 1
                elif num_1[i][1] >= 30:
                    start_idx = int(num_0[i][0] + num_1[i][0] + 28)
                    img_trans_3[start_idx:, i] = 0
                    count34 += 1

    print(f"第三轮处理: count31={count31}, count32={count32}, count33={count33}, count34={count34}")

    # K-means聚类
    print("开始K-means聚类...")
    kmeans = KMeans(n_clusters=11, random_state=42, n_init=10)
    idx = kmeans.fit_predict(img_trans_3.T)

    # 分类结果
    classification = {}
    for k in range(11):
        classification[k] = np.where(idx == k)[0]

    # 显示聚类结果
    print("\n聚类结果:")
    for k in range(11):
        print(f'Cluster {k + 1} has {len(classification[k])} elements.')
        if len(classification[k]) > 0:
            print(f'  包含图像索引: {classification[k].tolist()}')

    # ------------------------------
    # 对每个聚类进行拼接
    # ------------------------------
    print("\n开始对每个聚类进行拼接...")

    stitching_results = {}

    for k in range(11):
        cluster_indices = classification[k]
        if len(cluster_indices) > 1:  # 只有多于1个图像的聚类才需要拼接
            print(f"\n处理Cluster {k + 1}:")
            print(f"  图像数量: {len(cluster_indices)}")
            print(f"  原始索引: {cluster_indices.tolist()}")

            # 执行拼接
            optimal_order = stitch_cluster(img, cluster_indices)
            stitching_results[k] = optimal_order

            print(f"  最优拼接顺序: {optimal_order}")

            # 计算拼接质量评估
            if len(optimal_order) > 1:
                total_cost = 0
                for i in range(len(optimal_order) - 1):
                    curr_img = img[optimal_order[i]]
                    next_img = img[optimal_order[i + 1]]

                    curr_right = curr_img[:, -1].flatten().astype(np.float32)
                    next_left = next_img[:, 0].flatten().astype(np.float32)

                    cost = np.sum((curr_right - next_left) ** 2)
                    total_cost += cost

                avg_cost = total_cost / (len(optimal_order) - 1)
                print(f"  平均拼接代价: {avg_cost:.2f}")

        elif len(cluster_indices) == 1:
            print(f"\nCluster {k + 1} 只有1个图像，无需拼接")
            stitching_results[k] = cluster_indices.tolist()
        else:
            print(f"\nCluster {k + 1} 为空")
            stitching_results[k] = []

    # 输出汇总结果
    print("\n" + "=" * 50)
    print("拼接结果汇总:")
    print("=" * 50)

    for k in range(11):
        if len(stitching_results[k]) > 0:
            print(f"Cluster {k + 1}: {stitching_results[k]}")

    return img, img_trans_3, classification, idx, stitching_results


if __name__ == "__main__":
    try:
        img, img_trans_3, classification, idx, stitching_results = process_images()
        print("\n处理完成!")

        # 保存结果到文件
        print("\n保存拼接结果到 stitching_results.txt")
        with open("stitching_results.txt", "w", encoding="utf-8") as f:
            f.write("图像聚类与拼接结果\n")
            f.write("=" * 50 + "\n\n")

            for k in range(11):
                f.write(f"Cluster {k + 1}:\n")
                f.write(f"  图像数量: {len(classification[k])}\n")
                f.write(f"  原始索引: {classification[k].tolist()}\n")
                f.write(f"  拼接顺序: {stitching_results[k]}\n\n")

        # 启动交互式GUI
        print("\n启动交互式编辑器...")
        gui = InteractiveStitchingGUI(img, stitching_results, classification)
        gui.run()

    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        import traceback

        traceback.print_exc()