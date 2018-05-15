/**
 * A component that holds a single module that is then contained within the
 * Module Library.
 *
 * Rendered by ModuleCategories.
 *
 * The render function here will drive the "card" of each module within
 * the library.
 */

import React from 'react'
import PropTypes from 'prop-types'
import { DragSource } from 'react-dnd';
import { getEmptyImage } from 'react-dnd-html5-backend';
import debounce from 'lodash/debounce';
import { connect } from 'react-redux'
import { matchLessonHighlight } from './util/LessonHighlight'
import lessonSelector from './lessons/lessonSelector'

// TODO: gather all functions for dragging into one utility file
const spec = {
  beginDrag(props) {
    return {
      type: 'module',
      index: false,
      id: props.id,
      name: props.name,
      icon: props.icon,
      insert: true,
    }
  },
  endDrag(props, monitor) {
    if (monitor.didDrop()) {
      const result = monitor.getDropResult();
      props.dropModule(
        result.source.id,
        result.source.target,
        {
          name: result.source.name,
          icon: result.source.icon,
        }
      );
    }
  }
}

function collect(connect, monitor) {
  return {
    connectDragSource: connect.dragSource(),
    connectDragPreview: connect.dragPreview(),
    isDragging: monitor.isDragging()
  }
}

export class Module extends React.Component {
  constructor(props) {
    super(props);
    // debounce itemClick, because people have a tendency to double-click
    // the module names to add them.
    // We can't just capture the doubleClick event because the onClick handler
    // prevents us from doing so: https://stackoverflow.com/questions/25777826/onclick-works-but-ondoubleclick-is-ignored-on-react-component#25780754
    this.itemClick = debounce(this.itemClick.bind(this), 1000, {
      // Call the callback immediately, suppress subsequent calls
      leading: true,
      trailing: false
    });
  }

  itemClick(evt) {
    if (!this.props.isReadOnly)
      this.props.addModule(this.props.id, {
        name: this.props.name,
        icon: this.props.icon
      });
  }

  componentDidMount() {
    this.props.connectDragPreview(getEmptyImage(), {
			// IE fallback: specify that we'd rather screenshot the node
			// when it already knows it's being dragged so we can hide it with CSS.
			captureDraggingState: true,
		})
  }

  render() {
    const moduleName = this.props.name;
    const icon = `icon-${this.props.icon} ml-icon`;
    const className = `card ml-module-card ${this.props.isLessonHighlight ? 'lesson-highlight' : ''}`

    const moduleCard = (
      <div data-module-name={moduleName} className={className} onClick={this.itemClick}>
        <div className='ML-module d-flex'>
          <div className='d-flex flex-row align-items-center'>
            <div className='ml-icon-container'>
              <div className={icon} />
            </div>
            <div>
              <div className='content-5 ml-module-name'>{moduleName}</div>
            </div>
          </div>
          <div className='ml-handle'>
            <div className='icon-grip' />
          </div>
        </div>
      </div>
    )

    // Do not allow dragging if in Read-Only
    if (this.props.isReadOnly) {
      return moduleCard;
    } else {
      return this.props.connectDragSource(moduleCard);
    }
  }
}

Module.propTypes = {
  id:                 PropTypes.number.isRequired,
  name:               PropTypes.string.isRequired,
  icon:               PropTypes.string.isRequired,
  addModule:          PropTypes.func.isRequired,
  dropModule:         PropTypes.func.isRequired,
  isReadOnly:         PropTypes.bool.isRequired,
  isLessonHighlight:  PropTypes.bool.isRequired,
  connectDragSource:  PropTypes.func.isRequired,
  connectDragPreview: PropTypes.func.isRequired,
  isDragging:         PropTypes.bool.isRequired,
}

function mapStateToProps(state, ownProps) {
  const { testHighlight } = lessonSelector(state)
  return {
    isLessonHighlight: testHighlight({ type: 'MlModule', name: ownProps.name }),
  }
}

export default connect(
  mapStateToProps
)(DragSource('module', spec, collect)(Module))
