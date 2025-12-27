"""
QGIS Processing Script: Apply Bivariate Color Scheme
Applies bivariate color scheme to an already classified layer
Accepts custom colors as comma-separated hex codes
"""

from qgis.core import (QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterString,
                       QgsProcessingParameterField,
                       QgsProcessingException,
                       QgsCategorizedSymbolRenderer,
                       QgsRendererCategory,
                       QgsFillSymbol,
                       QgsLineSymbol,
                       QgsMarkerSymbol)
from qgis.PyQt.QtGui import QColor


class BivariateStylingAlgorithm(QgsProcessingAlgorithm):
    """
    Applies bivariate color scheme to a layer with Bi_Class field
    """
    
    INPUT = 'INPUT'
    CLASS_FIELD = 'CLASS_FIELD'
    COLORS = 'COLORS'
    OUTLINE_COLOR = 'OUTLINE_COLOR'
    OUTLINE_WIDTH = 'OUTLINE_WIDTH'
    
    def initAlgorithm(self, config=None):
        # Input vector layer
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                'Input layer with bivariate classes',
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        
        # Class field
        self.addParameter(
            QgsProcessingParameterField(
                self.CLASS_FIELD,
                'Bivariate class field',
                parentLayerParameterName=self.INPUT,
                defaultValue='Bi_Class'
            )
        )
        
        # Color scheme as comma-separated hex codes
        self.addParameter(
            QgsProcessingParameterString(
                self.COLORS,
                'Color scheme (9 hex codes: A1,A2,A3,B1,B2,B3,C1,C2,C3)',
                defaultValue='#e8e8e8,#dfb0d6,#be64ac,#ace4e4,#a5add3,#8c62aa,#5ac8c8,#5698b9,#3b4994',
                multiLine=False
            )
        )
        
        # Outline color
        self.addParameter(
            QgsProcessingParameterString(
                self.OUTLINE_COLOR,
                'Outline color (hex code)',
                defaultValue='#808080',
                optional=True
            )
        )
        
        # Outline width
        self.addParameter(
            QgsProcessingParameterString(
                self.OUTLINE_WIDTH,
                'Outline width',
                defaultValue='0.26',
                optional=True
            )
        )
    
    def processAlgorithm(self, parameters, context, feedback):
        # Get parameters
        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        class_field = self.parameterAsString(parameters, self.CLASS_FIELD, context)
        colors_string = self.parameterAsString(parameters, self.COLORS, context)
        outline_color = self.parameterAsString(parameters, self.OUTLINE_COLOR, context)
        outline_width = self.parameterAsString(parameters, self.OUTLINE_WIDTH, context)
        
        if layer is None:
            raise QgsProcessingException('Invalid input layer')
        
        feedback.pushInfo('Applying bivariate color scheme...')
        feedback.pushInfo(f'Class field: {class_field}')
        
        # Parse colors
        colors_list = [c.strip() for c in colors_string.split(',')]
        
        if len(colors_list) != 9:
            raise QgsProcessingException(
                f'Expected 9 colors, got {len(colors_list)}. '
                'Provide colors as: #color1,#color2,#color3,#color4,#color5,#color6,#color7,#color8,#color9'
            )
        
        # Validate hex colors
        for i, color in enumerate(colors_list):
            if not color.startswith('#'):
                raise QgsProcessingException(
                    f'Color {i+1} "{color}" must start with #'
                )
            if len(color) not in [4, 7]:  # #RGB or #RRGGBB
                raise QgsProcessingException(
                    f'Color {i+1} "{color}" is not a valid hex color'
                )
        
        # Map colors to bivariate classes
        # Order: A1, A2, A3, B1, B2, B3, C1, C2, C3
        class_names = ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
        color_map = dict(zip(class_names, colors_list))
        
        feedback.pushInfo('\nColor mapping:')
        for cls, color in color_map.items():
            feedback.pushInfo(f'  {cls}: {color}')
        
        # Check if class field exists
        if class_field not in [field.name() for field in layer.fields()]:
            raise QgsProcessingException(
                f'Field "{class_field}" not found in layer. '
                f'Available fields: {", ".join([f.name() for f in layer.fields()])}'
            )
        
        # Apply styling
        self.apply_bivariate_style(
            layer, 
            class_field, 
            color_map, 
            outline_color, 
            outline_width, 
            feedback
        )
        
        feedback.pushInfo('\n✓ Bivariate color scheme applied successfully!')
        feedback.pushInfo(f'✓ Layer "{layer.name()}" has been styled')
        
        return {}
    
    def apply_bivariate_style(self, layer, class_field, color_map, outline_color, outline_width, feedback):
        """Apply categorized symbology with bivariate colors"""
        categories = []
        
        # Determine geometry type
        geom_type = layer.geometryType()
        
        for bi_class, color_hex in color_map.items():
            # Create appropriate symbol based on geometry type
            if geom_type == 2:  # Polygon
                symbol = QgsFillSymbol.createSimple({
                    'color': color_hex,
                    'outline_color': outline_color,
                    'outline_width': outline_width,
                    'outline_style': 'solid'
                })
            elif geom_type == 1:  # Line
                symbol = QgsLineSymbol.createSimple({
                    'color': color_hex,
                    'width': outline_width
                })
            else:  # Point
                symbol = QgsMarkerSymbol.createSimple({
                    'color': color_hex,
                    'outline_color': outline_color,
                    'outline_width': outline_width,
                    'size': '3'
                })
            
            category = QgsRendererCategory(bi_class, symbol, bi_class)
            categories.append(category)
        
        # Create and apply renderer
        renderer = QgsCategorizedSymbolRenderer(class_field, categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        
        feedback.pushInfo(f'Applied {len(categories)} color categories')
    
    def name(self):
        return 'applybivariatecolors'
    
    def displayName(self):
        return 'Apply Bivariate Color Scheme'
    
    def group(self):
        return 'Cartography'
    
    def groupId(self):
        return 'cartography'
    
    def shortHelpString(self):
        return """
        Applies bivariate color scheme to a layer that already has bivariate classification.
        
        This tool is for styling a layer that already has a bivariate class field 
        (typically created by the "Bivariate Choropleth Classification" tool).
        
        Parameters:
        -----------
        Input layer: Layer with bivariate classes (A1-C3)
        
        Bivariate class field: Field containing class codes (default: Bi_Class)
        
        Color scheme: 9 comma-separated hex colors in order:
            A1, A2, A3, B1, B2, B3, C1, C2, C3
            
        Grid layout:
               Variable 2 (Horizontal) →
               A      B      C
            3  A3     B3     C3    ← High Var 1
            2  A2     B2     C2
            1  A1     B1     C1    ← Low Var 1
               ↑             ↑
              Low          High
            Variable 2
        
        Example color schemes:
        
        Purple-Orange:
        #e8e8e8,#dfb0d6,#be64ac,#ace4e4,#a5add3,#8c62aa,#5ac8c8,#5698b9,#3b4994
        
        Blue-Red:
        #e8e8e8,#e4acac,#c85a5a,#b0d5df,#ad9ea5,#985356,#64acbe,#627f8c,#574249
        
        Green-Blue:
        #e8e8e8,#b8d6be,#73ae80,#b5c0da,#90b2b3,#5a9178,#6c83b5,#567994,#2a5a5b
        
        Tips:
        - Use colorbrewer2.org to create custom schemes
        - A1 should be light/neutral (low-low)
        - C3 should be dark/saturated (high-high)
        - Ensure colors are distinguishable
        """
    
    def createInstance(self):
        return BivariateStylingAlgorithm()
