class style:

    # 输入框样式
    input_box = """
        QLineEdit {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 8px 12px;
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            font-size: 14px;
            color: #333333;
        }
        QLineEdit:focus {
            border-color: #0078d4;
            outline: none;
        }
    """

    # 托盘菜单样式
    tray_menu = """
        QMenu {
            background-color: rgba(255, 255, 255, 0.9); 
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 8px;
            font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
            font-size: 14px;
            font-weight: bold;
            color: #333333;
        }
        QMenu::item {
            background-color: transparent;
            padding: 8px 20px 8px 15px;
            border-radius: 4px;
            margin: 2px;
        }
        QMenu::item:selected {
            background-color: #f0f8ff;
            color: #0078d4;
        }
        QMenu::item:checked {
            background-color: #e8f5e8;
            color: #2d5016;
        }
        QMenu::separator {
            height: 1px;
            background-color: #e0e0e0;
            margin: 8px 10px;
        }
    """