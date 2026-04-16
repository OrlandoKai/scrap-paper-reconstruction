import cv2
import numpy as np
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import threading


class InteractiveImageStitcher:
    def __init__(self):
        self.pieces = []
        self.image_files = []
        self.original_images = []
        self.current_order = []
        self.stitched_result = None
        self.image_widgets = []  # 存储图片widget引用
        self.drag_data = None  # 拖拽数据
        self.gap_height = 2  # 图片之间的缝隙高度
        self.locked_groups = []  # 存储锁定的图片组
        self.selection_mode = False  # 是否处于选择模式
        self.selected_indices = set()  # 当前选中的图片索引

        # GUI 初始化
        self.root = tk.Tk()
        self.root.title("交互式图像拼接工具")
        self.root.geometry("1000x900")

        self.setup_gui()

    def setup_gui(self):
        """设置GUI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制面板
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        ttk.Button(control_frame, text="加载图片", command=self.load_images).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="自动拼接", command=self.auto_stitch).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="重置顺序", command=self.reset_order).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="保存结果", command=self.save_result).pack(side=tk.LEFT, padx=5)

        # 锁定功能控制面板
        lock_frame = ttk.Frame(main_frame)
        lock_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))

        # 选择模式按钮
        self.select_mode_var = tk.BooleanVar()
        select_checkbox = ttk.Checkbutton(lock_frame, text="选择模式",
                                          variable=self.select_mode_var,
                                          command=self.toggle_selection_mode)
        select_checkbox.pack(side=tk.LEFT, padx=5)

        ttk.Button(lock_frame, text="锁定选中", command=self.lock_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(lock_frame, text="解锁所有", command=self.unlock_all).pack(side=tk.LEFT, padx=5)

        # 锁定组显示
        self.lock_status_var = tk.StringVar()
        self.lock_status_var.set("无锁定组")
        lock_status_label = ttk.Label(lock_frame, textvariable=self.lock_status_var)
        lock_status_label.pack(side=tk.LEFT, padx=10)

        # 说明标签
        instruction_label = ttk.Label(main_frame,
                                      text="拖拽图片调整顺序 | 勾选选择模式后点击图片选择，然后锁定选中的图片组",
                                      font=('Arial', 10), foreground='gray')
        instruction_label.pack(pady=(0, 5))

        # 主预览区域 - 单栏布局
        preview_frame = ttk.LabelFrame(main_frame, text="拼接预览 (可拖拽调整)", padding=5)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        # 创建可滚动的Canvas
        canvas_frame = ttk.Frame(preview_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.preview_canvas = tk.Canvas(canvas_frame, bg='#f0f0f0')

        # 滚动条
        v_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.preview_canvas.yview)
        h_scrollbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.preview_canvas.xview)

        self.preview_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # 布局
        self.preview_canvas.pack(side="left", fill="both", expand=True)
        v_scrollbar.pack(side="right", fill="y")
        h_scrollbar.pack(side="bottom", fill="x")

        # 创建Canvas内的Frame来放置图片
        self.canvas_frame = tk.Frame(self.preview_canvas, bg='#f0f0f0')
        self.canvas_window = self.preview_canvas.create_window((0, 0), window=self.canvas_frame, anchor="nw")

        # 绑定Canvas大小调整事件
        self.canvas_frame.bind("<Configure>", self.on_canvas_configure)
        self.preview_canvas.bind("<Configure>", self.on_preview_canvas_configure)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("请先加载图片")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

    def toggle_selection_mode(self):
        """切换选择模式"""
        self.selection_mode = self.select_mode_var.get()
        if not self.selection_mode:
            self.selected_indices.clear()
        self.update_display()

    def lock_selected(self):
        """锁定选中的图片"""
        if len(self.selected_indices) < 2:
            messagebox.showwarning("警告", "请至少选择2张图片进行锁定")
            return

        # 按顺序排列选中的索引
        selected_list = sorted(self.selected_indices)

        # 检查是否连续
        is_continuous = True
        for i in range(len(selected_list) - 1):
            if selected_list[i + 1] - selected_list[i] != 1:
                is_continuous = False
                break

        if not is_continuous:
            if not messagebox.askyesno("确认", "选中的图片不连续，确定要锁定吗？"):
                return

        # 添加到锁定组
        self.locked_groups.append(list(selected_list))
        self.selected_indices.clear()
        self.select_mode_var.set(False)
        self.selection_mode = False

        self.update_lock_status()
        self.update_display()

    def unlock_all(self):
        """解锁所有图片组"""
        self.locked_groups.clear()
        self.update_lock_status()
        self.update_display()

    def update_lock_status(self):
        """更新锁定状态显示"""
        if not self.locked_groups:
            self.lock_status_var.set("无锁定组")
        else:
            status = f"锁定组: "
            for i, group in enumerate(self.locked_groups):
                if i > 0:
                    status += ", "
                status += f"组{i + 1}({len(group)}张)"
            self.lock_status_var.set(status)

    def get_locked_group(self, order_index):
        """获取指定索引所属的锁定组"""
        for group in self.locked_groups:
            if order_index in group:
                return group
        return None

    def on_canvas_configure(self, event):
        """Canvas内容大小改变时更新滚动区域"""
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def on_preview_canvas_configure(self, event):
        """预览Canvas大小改变时调整内部frame宽度"""
        canvas_width = event.width
        self.preview_canvas.itemconfig(self.canvas_window, width=canvas_width)

    def preprocess(self, image_path):
        """读取并二值化图像"""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"图像文件 {image_path} 未找到")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        return binary

    def extract_edges(self, img, width=1):
        """提取上下边缘特征（横图拼接）"""
        top = img[:width, :].flatten().astype(np.float32)
        bottom = img[-width:, :].flatten().astype(np.float32)
        return top, bottom

    def compute_cost_matrix(self, pieces):
        """计算碎片间匹配代价矩阵"""
        n = len(pieces)
        cost = np.full((n, n), np.inf)

        for i in range(n):
            for j in range(n):
                if i != j:
                    cost[i, j] = np.sum((pieces[i]['bottom'] - pieces[j]['top']) ** 2)

        return cost

    def find_optimal_order(self, cost_matrix, pieces):
        """动态规划求解最优排列"""
        n = cost_matrix.shape[0]
        INF = float('inf')

        dp = [[INF] * n for _ in range(1 << n)]
        prev = [[-1] * n for _ in range(1 << n)]

        start = np.argmax([np.mean(p['top']) for p in pieces])
        dp[1 << start][start] = 0

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

    def load_images(self):
        """加载图片"""
        try:
            folder_path = filedialog.askdirectory(title="选择包含图片的文件夹")
            if not folder_path:
                return

            self.pieces = []
            self.image_files = []
            self.original_images = []
            self.locked_groups = []
            self.selected_indices.clear()

            # 查找所有图片文件
            for i in range(1, 20):  # 扩大搜索范围
                found = False
                for ext in ['.jpg', '.png', '.bmp', '.jpeg']:
                    for pattern in [f'cluster_{i}_stitch', f'cluster_{i}_stitched', f'cluster_{i}']:
                        file_path = os.path.join(folder_path, pattern + ext)
                        if os.path.exists(file_path):
                            self.status_var.set(f"正在处理: {os.path.basename(file_path)}")
                            self.root.update()

                            img = self.preprocess(file_path)
                            top, bottom = self.extract_edges(img)
                            self.pieces.append({'top': top, 'bottom': bottom})
                            self.image_files.append(file_path)

                            # 保存原始图像用于显示
                            original_img = cv2.imread(file_path)
                            self.original_images.append(original_img)
                            found = True
                            break
                    if found:
                        break

            if not self.pieces:
                messagebox.showerror("错误", "在选定文件夹中未找到任何图片文件")
                return

            self.current_order = list(range(len(self.pieces)))
            self.create_stitched_preview()
            self.status_var.set(f"成功加载 {len(self.pieces)} 张图片")
            self.update_lock_status()

        except Exception as e:
            messagebox.showerror("错误", f"加载图片时出错: {str(e)}")

    def create_stitched_preview(self):
        """创建拼接预览，图片之间有细缝隙"""
        # 清空现有内容
        for widget in self.canvas_frame.winfo_children():
            widget.destroy()

        self.image_widgets = []

        if not self.original_images:
            return

        # 计算统一的显示宽度
        canvas_width = self.preview_canvas.winfo_width()
        if canvas_width <= 1:
            canvas_width = 800  # 默认宽度

        display_width = canvas_width - 40  # 留出边距

        current_y = 10  # 起始Y位置

        for i, idx in enumerate(self.current_order):
            # 如果不是第一张图片，添加分隔缝隙
            if i > 0:
                gap_frame = tk.Frame(self.canvas_frame, height=self.gap_height, bg='#d0d0d0')
                gap_frame.pack(fill=tk.X, pady=0)
                current_y += self.gap_height

            # 处理图片
            img = self.original_images[idx]
            h, w = img.shape[:2]

            # 计算缩放比例以适应显示宽度
            scale = display_width / w
            new_w = int(w * scale)
            new_h = int(h * scale)

            img_resized = cv2.resize(img, (new_w, new_h))

            # 转换为PIL图像
            img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            photo = ImageTk.PhotoImage(pil_img)

            # 确定容器背景色
            bg_color = self.get_container_bg_color(i)

            # 创建图片容器
            img_container = tk.Frame(self.canvas_frame, bg=bg_color, relief=tk.RAISED, bd=2)
            img_container.pack(fill=tk.X, padx=10, pady=0)

            # 创建图片标签
            img_label = tk.Label(img_container, image=photo, bg=bg_color, cursor='hand2')
            img_label.image = photo  # 保持引用
            img_label.pack(side=tk.TOP, pady=2)

            # 统一添加所有功能，根据模式决定行为
            self.add_interaction_functionality(img_container, img_label, i)

            self.image_widgets.append({
                'container': img_container,
                'img_label': img_label,
                'index': idx,
                'order_index': i
            })

            current_y += new_h + 10

        # 更新滚动区域
        self.canvas_frame.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def get_container_bg_color(self, order_index):
        """根据图片状态获取容器背景色"""
        if self.selection_mode and order_index in self.selected_indices:
            return '#ffeb3b'  # 选中状态：黄色

        # 检查是否属于锁定组
        for group_idx, group in enumerate(self.locked_groups):
            if order_index in group:
                colors = ['#e3f2fd', '#f3e5f5', '#e8f5e8', '#fff3e0', '#fce4ec']  # 不同组的颜色
                return colors[group_idx % len(colors)]

        return 'white'  # 默认背景色

    def add_interaction_functionality(self, container, img_label, order_index):
        """为图片添加交互功能（选择或拖拽）"""

        def on_click(event):
            if self.selection_mode:
                # 选择模式：切换选中状态
                if order_index in self.selected_indices:
                    self.selected_indices.remove(order_index)
                else:
                    self.selected_indices.add(order_index)
                self.update_display()
            # 非选择模式时，click事件用于拖拽开始，不做其他处理

        def on_drag_start(event):
            if self.selection_mode:
                return  # 选择模式下不允许拖拽

            # 检查是否属于锁定组
            locked_group = self.get_locked_group(order_index)

            self.drag_data = {
                'order_index': order_index,
                'container': container,
                'start_y': event.y_root,
                'original_bg': container.cget('bg'),
                'locked_group': locked_group,
                'is_dragging': False  # 标记是否真正开始拖拽
            }

            img_label.configure(cursor='hand1')

        def on_drag_motion(event):
            if self.selection_mode or not self.drag_data:
                return

            if self.drag_data['container'] == container:
                # 检查是否移动了足够距离才开始拖拽
                if not self.drag_data['is_dragging']:
                    if abs(event.y_root - self.drag_data['start_y']) > 5:  # 移动超过5像素才开始拖拽
                        self.drag_data['is_dragging'] = True
                        locked_group = self.drag_data['locked_group']

                        # 高亮被拖拽的项（包括整个锁定组）
                        if locked_group:
                            for idx in locked_group:
                                for widget_info in self.image_widgets:
                                    if widget_info['order_index'] == idx:
                                        widget_info['container'].configure(bg='#ffcccc', relief=tk.SUNKEN)
                        else:
                            container.configure(bg='#ffffcc', relief=tk.SUNKEN)

                if self.drag_data['is_dragging']:
                    self.highlight_drop_zone(event.y_root)

        def on_drag_end(event):
            if self.selection_mode or not self.drag_data:
                return

            if self.drag_data['container'] == container:
                if self.drag_data['is_dragging']:
                    # 只有真正拖拽了才移动
                    new_pos = self.calculate_drop_position(event.y_root)
                    old_pos = self.drag_data['order_index']
                    locked_group = self.drag_data['locked_group']

                    if new_pos != old_pos and 0 <= new_pos < len(self.current_order):
                        if locked_group:
                            # 移动整个锁定组
                            self.move_locked_group(locked_group, new_pos)
                        else:
                            # 移动单个图片
                            item = self.current_order.pop(old_pos)
                            self.current_order.insert(new_pos, item)
                            # 更新所有锁定组的索引
                            self.update_locked_groups_after_single_move(old_pos, new_pos)

                        self.create_stitched_preview()

                # 重置样式
                self.clear_highlights()
                img_label.configure(cursor='hand2')
                self.drag_data = None

        def on_double_click(event):
            if self.selection_mode:
                return  # 选择模式下不允许双击操作

            locked_group = self.get_locked_group(order_index)

            if locked_group:
                # 移动整个锁定组
                min_idx = min(locked_group)
                if min_idx == 0:
                    # 移到底部
                    self.move_locked_group(locked_group, len(self.current_order))
                else:
                    # 移到顶部
                    self.move_locked_group(locked_group, 0)
            else:
                # 移动单个图片
                if order_index == 0:
                    item = self.current_order.pop(order_index)
                    self.current_order.append(item)
                    self.update_locked_groups_after_single_move(order_index, len(self.current_order) - 1)
                else:
                    item = self.current_order.pop(order_index)
                    self.current_order.insert(0, item)
                    self.update_locked_groups_after_single_move(order_index, 0)

            self.create_stitched_preview()

        # 绑定事件
        for widget in [container, img_label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Button-1>", on_drag_start, add='+')  # 添加到现有绑定
            widget.bind("<B1-Motion>", on_drag_motion)
            widget.bind("<ButtonRelease-1>", on_drag_end)
            widget.bind("<Double-Button-1>", on_double_click)

    def update_locked_groups_after_single_move(self, old_pos, new_pos):
        """单个图片移动后更新所有锁定组的索引"""
        for group in self.locked_groups:
            updated_group = []
            for idx in group:
                if idx == old_pos:
                    # 被移动的图片
                    updated_group.append(new_pos)
                elif old_pos < new_pos:
                    # 向后移动，中间的索引需要前移
                    if old_pos < idx <= new_pos:
                        updated_group.append(idx - 1)
                    else:
                        updated_group.append(idx)
                else:
                    # 向前移动，中间的索引需要后移
                    if new_pos <= idx < old_pos:
                        updated_group.append(idx + 1)
                    else:
                        updated_group.append(idx)
            group[:] = updated_group  # 原地更新列表

    def update_display(self):
        """更新显示状态"""
        for widget_info in self.image_widgets:
            order_index = widget_info['order_index']
            bg_color = self.get_container_bg_color(order_index)
            widget_info['container'].configure(bg=bg_color)
            widget_info['img_label'].configure(bg=bg_color)

    def move_locked_group(self, locked_group, target_pos):
        """移动锁定组"""
        # 按当前顺序排序锁定组
        group_in_order = sorted(locked_group)

        # 计算实际插入位置
        if target_pos > max(group_in_order):
            # 向后移动，插入位置需要调整
            actual_target = target_pos - len(group_in_order)
        else:
            # 向前移动或在组内移动
            actual_target = min(target_pos, min(group_in_order))

        # 提取锁定组的元素
        group_items = []
        for idx in reversed(group_in_order):  # 从后往前删除以保持索引正确
            group_items.insert(0, self.current_order.pop(idx))

        # 插入到新位置
        for i, item in enumerate(group_items):
            self.current_order.insert(actual_target + i, item)

        # 更新锁定组索引
        for i, group in enumerate(self.locked_groups):
            if set(group) == set(locked_group):  # 找到对应的锁定组
                new_indices = list(range(actual_target, actual_target + len(group_items)))
                self.locked_groups[i] = new_indices
                break

        # 更新其他锁定组的索引
        self.update_other_locked_groups_after_group_move(group_in_order, actual_target, len(group_items))

    def update_other_locked_groups_after_group_move(self, moved_group_old_indices, new_start, group_size):
        """锁定组移动后更新其他锁定组的索引"""
        old_min = min(moved_group_old_indices)
        old_max = max(moved_group_old_indices)
        new_end = new_start + group_size - 1

        for group in self.locked_groups:
            # 跳过已经更新过的移动组
            if set(group) == set(range(new_start, new_start + group_size)):
                continue

            updated_group = []
            for idx in group:
                new_idx = idx

                if old_min <= idx <= old_max:
                    # 这个索引是移动组的一部分，应该已经被处理了
                    continue
                elif new_start <= new_end:
                    # 组向前移动或位置重叠的情况
                    if idx < old_min:
                        if idx >= new_start:
                            new_idx = idx + group_size
                    elif idx > old_max:
                        if new_end >= old_max:
                            new_idx = idx - group_size
                        else:
                            if idx <= new_end:
                                new_idx = idx + group_size

                updated_group.append(new_idx)

            group[:] = updated_group

    def highlight_drop_zone(self, y_pos):
        """高亮显示可能的插入位置"""
        drop_pos = self.calculate_drop_position(y_pos)
        self.clear_highlights()

        if 0 <= drop_pos < len(self.image_widgets):
            self.image_widgets[drop_pos]['container'].configure(bg='#e0ffe0')

    def clear_highlights(self):
        """清除所有高亮"""
        for widget_info in self.image_widgets:
            if not self.drag_data or widget_info['container'] != self.drag_data['container']:
                order_index = widget_info['order_index']
                bg_color = self.get_container_bg_color(order_index)
                widget_info['container'].configure(bg=bg_color, relief=tk.RAISED)

    def calculate_drop_position(self, y_pos):
        """根据鼠标位置计算放置位置"""
        try:
            canvas_top = self.preview_canvas.winfo_rooty()
            scroll_top = self.preview_canvas.canvasy(0)
            relative_y = y_pos - canvas_top + scroll_top

            for i, widget_info in enumerate(self.image_widgets):
                container = widget_info['container']
                container_y = container.winfo_y()
                container_height = container.winfo_height()

                if relative_y <= container_y + container_height / 2:
                    return i

            return len(self.image_widgets) - 1
        except:
            return 0

    def reset_order(self):
        """重置为原始顺序"""
        if self.pieces:
            self.current_order = list(range(len(self.pieces)))
            self.locked_groups.clear()
            self.selected_indices.clear()
            self.create_stitched_preview()
            self.update_lock_status()
            self.status_var.set("已重置为原始顺序")

    def auto_stitch(self):
        """自动拼接"""
        if not self.pieces:
            messagebox.showwarning("警告", "请先加载图片")
            return

        try:
            self.status_var.set("计算最优拼接顺序...")
            self.root.update()

            def compute_order():
                cost_matrix = self.compute_cost_matrix(self.pieces)
                order = self.find_optimal_order(cost_matrix, self.pieces)
                self.root.after(0, lambda: self.finish_auto_stitch(order))

            thread = threading.Thread(target=compute_order)
            thread.daemon = True
            thread.start()

        except Exception as e:
            messagebox.showerror("错误", f"自动拼接时出错: {str(e)}")

    def finish_auto_stitch(self, order):
        """完成自动拼接"""
        self.current_order = order
        self.locked_groups.clear()
        self.selected_indices.clear()
        self.create_stitched_preview()
        self.update_lock_status()
        self.status_var.set("自动拼接完成")

    def save_result(self):
        """保存拼接结果"""
        if not self.original_images:
            messagebox.showwarning("警告", "请先加载图片")
            return

        try:
            result = None
            for idx in self.current_order:
                img = self.original_images[idx]
                if result is None:
                    result = img
                else:
                    result = np.vstack((result, img))

            file_path = filedialog.asksaveasfilename(
                defaultextension=".jpg",
                filetypes=[("JPEG files", "*.jpg"), ("PNG files", "*.png"), ("All files", "*.*")]
            )

            if file_path:
                cv2.imwrite(file_path, result)
                messagebox.showinfo("成功", f"拼接结果已保存为 {file_path}")
                self.status_var.set(f"已保存: {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("错误", f"保存文件时出错: {str(e)}")

    def run(self):
        """运行应用程序"""
        self.root.mainloop()


if __name__ == "__main__":
    app = InteractiveImageStitcher()
    app.run()