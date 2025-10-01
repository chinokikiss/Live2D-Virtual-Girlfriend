class style:

    # 输入框样式
    input_box = """
        QLineEdit {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 10px 14px;
            font-family: '%s', 'Segoe UI', sans-serif;
            font-size: 16px;
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
            font-family: '%s', 'Segoe UI', sans-serif;
            font-size: 16px;
            font-weight: bold;
            color: #333333;
        }
        QMenu::item {
            background-color: transparent;
            padding: 10px 22px 10px 17px;
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

    # 右键菜单样式
    context_menu = """
        QMenu {
            background-color: rgba(255, 255, 255, 240);
            border: 2px solid rgba(200, 200, 200, 180);
            border-radius: 12px;
            font-family: '%s';
            font-size: 16px;
            padding: 8px 0px;
            color: black;
        }
        QMenu::item {
            padding: 12px 20px;
            margin: 2px 6px;
            border-radius: 8px;
            background-color: transparent;
            color: black;
        }
        QMenu::item:selected {
            background-color: rgba(200, 200, 200, 100);
            color: black;
        }
        QMenu::item:pressed {
            background-color: rgba(200, 200, 200, 150);
        }
        QMenu::separator {
            height: 1px;
            background-color: rgba(150, 150, 150, 100);
            margin: 6px 12px;
        }
    """