import React from 'react'
import PropTypes from 'prop-types'
import WorkbenchAPI from '../../WorkbenchAPI'
import {CirclePicker} from 'react-color'

var api = WorkbenchAPI();
export function mockAPI(mock_api) {
    api = mock_api;
}

// Classes in these modules are used in testing.
// If they are changed, please update the tests accordingly.

export class SingleMapLayerEditor extends React.Component {
    static propTypes = {
        column: PropTypes.string.isRequired,
        levels: PropTypes.number.isRequired,
        color: PropTypes.string.isRequired,
        selected: PropTypes.bool.isRequired,
        onEdit: PropTypes.func.isRequired,
        isReadOnly: PropTypes.bool.isRequired,
    };

    constructor(props) {
        super(props);

        this.state = {
            selected: this.props.selected,
            levels: this.props.levels,
            color: this.props.color,
        }
    }

    handleCheckboxClick = () => {
        this.setState({selected: !this.state.selected}, () => {
            this.props.onEdit(this.props.column, {
                color: this.props.color,
                levels: parseInt(this.state.levels),
                selected: this.state.selected
            });
        });
    };

    handleInputChange = (event) => {
        this.setState({levels: event.target.value});
    };

    commitInputValue = () => {
        console.log("New levels: " + this.state.levels);
        this.props.onEdit(this.props.column, {
            color: this.props.color,
            levels: parseInt(this.state.levels),
            selected: this.props.selected,
        });
    };

    handleInputBlur = () => {
        if(this.state.levels !== this.props.levels) {
            this.commitInputValue();
        }
    };

    handleInputKeyPress = (event) => {
        if((event.key == 'Enter') && (this.state.levels !== this.props.levels)) {
            this.commitInputValue();
        }
    };

    handleInputFocus = (event) => {
        event.target.select();
    };

    handleColorChangeComplete = (color, event) => {
        console.log("New color: " + color.hex);
        if(this.props.isReadOnly) {
            this.setState({color: this.props.color});
        } else {
            this.setState({color: color.hex}, () => {
                this.props.onEdit(this.props.column, {
                    color: color.hex,
                    levels: parseInt(this.state.levels),
                    selected: this.props.selected,
                });
            });
        }

    };

    render() {
        return (
            <div className="map-single-layer-editor">
                <div>
                    <input
                        type={"checkbox"}
                        checked={this.state.selected}
                        onChange={this.handleCheckboxClick}
                        className={"map-layer-checkbox"}
                        disabled={this.props.isReadOnly}
                    />
                    <span>{this.props.column}</span>
                    <input
                        type={"text"}
                        value={this.state.levels}
                        onChange={this.handleInputChange}
                        onBlur={this.handleInputBlur}
                        onFocus={this.handleInputFocus}
                        onKeyPress={this.handleInputKeyPress}
                        className={"map-layer-levels-input"}
                        disabled={this.props.isReadOnly}
                    />
                    <span className={"map-layer-levels-label"}>levels</span>
                </div>
                <CirclePicker
                    width={"240px"}
                    color={this.state.color}
                    colors={['#F44336', '#FF9800', '#FFEB3B', '#4CAF50', '#009688', '#2196F3', '#9C27B0', '#607D8B']}
                    circleSpacing={6}
                    circleSize={24}
                    onChangeComplete={this.handleColorChangeComplete}
                />
            </div>
        )
    }
}

export default class MapLayerEditor extends React.Component {
    /*
        ParamData format after JSON parsing:
        {
            lastEdited: <column>
            layers: <dictionary of <colname>: selected, levels, color>
        }
     */

    static propTypes = {
        name: PropTypes.string.isRequired,
        paramId: PropTypes.number.isRequired,
        keyColumn: PropTypes.string.isRequired,
        wfModuleId: PropTypes.number.isRequired,
        isReadOnly: PropTypes.bool.isRequired,
        paramData: PropTypes.string.isRequired,
    };

    constructor(props) {
        super(props);

        let data = this.parseParamData(props.paramData);

        this.state = {
            columns: [],
            data: data,
        }
    }

    parseParamData(dataStr) {
        let data = {};
        try {
            data = JSON.parse(dataStr)
        } catch(e) {
            data = {
                lastEdited: undefined,
                layers: {}
            }
        }

        return data;
    }

    componentDidMount() {
        api.inputColumns(this.props.wfModuleId).then((result) => {
            let newData = Object.assign(this.state.data);

            // We update the server whenever new columns are added,
            // including when the module first loads.
            let updateData = false;
            result.forEach((col) => {
                if(!(col in newData.layers)) {
                    newData.layers[col] = {
                        selected: true,
                        levels: 5,
                        color: '#F44336'
                    };
                    updateData = true;
                }
            });

            this.setState({
                columns: result,
                data: newData
            });

            if(updateData) {
                console.log('Data updated');
                api.onParamChanged(this.props.paramId, {value: JSON.stringify(newData)});
            }
        });
    }

    handleLayerEdit = (col, props) => {
        let newData = Object.assign({}, this.state.data);
        newData.layers[col] = Object.assign({}, props);
        newData.lastEdited = col;
        this.setState({data: newData});
        api.onParamChanged(this.props.paramId, {value: JSON.stringify(newData)});
    };

    render() {
        // We don't render anything visible if no location column is selected
        if(this.props.keyColumn.trim() == '') {
            return (<div></div>);
        }

        const columns = this.state.columns.filter((col) => {
            return (col !== this.props.keyColumn);
        }).map((col) => {
            return (
                <SingleMapLayerEditor
                    key={col}
                    column={col}
                    color={this.state.data.layers[col].color}
                    levels={this.state.data.layers[col].levels}
                    selected={this.state.data.layers[col].selected}
                    onEdit={this.handleLayerEdit}
                    isReadOnly={this.props.isReadOnly}
                />
            )
        });

        return (
            <div>
                <div className='label-margin t-d-gray content-3'>{this.props.name}</div>
                <div>{columns}</div>
            </div>
        )
    }
}